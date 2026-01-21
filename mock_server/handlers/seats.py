"""Seat selection handlers (Step 7).

Provides stateful seat selection/preselect endpoints required by the booking UI.

Contract mapping:
- selectSeats / deleteShoppingCartSeats -> ShoppingCartResponse
- getSeatsPreselect / getPreseatSuggestion -> SeatsPreselectResponse
- updateSpecialAssistanceSeats -> SpecialAssistanceSeatsResponse

Design goals:
- never fail the flow: always HTTP 200
- persist seat selections in state store
- reflect seat fees in cart pricing
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ..headers import RequestContext, build_request_context
from ..responses import ok, with_context_warnings
from ..state import MockStateStore
from ..versioning import now_utc_iso, stable_id

from .flights_search import _build_shopping_cart_payload, _make_pricing, _safe_json


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _extract_seat_selections(payload: Any) -> list[dict[str, Any]]:
    """Extract SeatSelection-like dicts from request bodies.

    Supported request shapes:
    - SeatsSelectionRequest: {"seatSelections": [SeatSelection, ...]}
    - AncillariesUpdateRequest: {"seatSelections": [...], ...}
    """

    if not isinstance(payload, dict):
        return []

    raw = payload.get("seatSelections")
    if isinstance(raw, dict):
        raw_list = [raw]
    else:
        raw_list = _safe_list(raw)

    out: list[dict[str, Any]] = []
    for item in raw_list:
        d = _safe_json(item)
        if not d:
            continue
        out.append(
            {
                "passengerId": str(d.get("passengerId") or "").strip(),
                "segmentId": str(d.get("segmentId") or "").strip(),
                "rowNumber": str(d.get("rowNumber") or "").strip(),
                "seatNumber": str(d.get("seatNumber") or "").strip(),
                "priorityMember": d.get("priorityMember"),
                "priorityClassicMember": d.get("priorityClassicMember"),
                "specialAssistance": d.get("specialAssistance"),
                "redemption": d.get("redemption"),
                "usePoints": d.get("usePoints"),
                "smiFree": d.get("smiFree"),
            }
        )
    return out


def _seat_price(row_number: str, seat_number: str) -> float:
    """Seat fee aligned with handlers.cabins seat type rules."""

    try:
        r = int(str(row_number).strip())
    except Exception:  # noqa: BLE001
        return 0.0

    col = str(seat_number).strip().upper()

    # Business and most premium seats are free.
    if 1 <= r <= 9:
        return 0.0
    if 10 <= r <= 14:
        # Premium XL (row 10 D/F).
        if r == 10 and col in {"D", "F"}:
            return 25.0
        return 0.0

    # Economy exit/XL rows.
    if r in {15, 40} and col in {"D", "F", "G"}:
        return 25.0
    if r in {15, 40} and col in {"A", "B", "C", "H", "J", "K"}:
        return 30.0

    return 0.0


def _compute_flights_total(search_obj: dict[str, Any]) -> tuple[float, str]:
    """Compute flight total from stored flights_search selection."""

    total_amount = 0.0
    currency = "USD"
    option_sets = search_obj.get("optionSets")
    if not isinstance(option_sets, list):
        return 0.0, currency

    for os_ in option_sets:
        option_set = _safe_json(os_)
        sel = _safe_json(option_set.get("selection"))
        option_id = str(sel.get("optionId") or option_set.get("optionId") or "")
        solution_id = str(sel.get("solutionId") or option_set.get("solutionId") or "")
        if not option_id:
            continue

        options = option_set.get("options")
        if not isinstance(options, list):
            continue

        option_obj: dict[str, Any] | None = None
        for opt in options:
            od = _safe_json(opt)
            if str(od.get("id")) == option_id:
                option_obj = od
                break
        if option_obj is None:
            continue

        if not solution_id:
            solution_id = str(option_obj.get("cheapestSolutionId") or "")

        solutions = option_obj.get("solutions")
        if not isinstance(solutions, dict):
            continue
        sol = solutions.get(solution_id)
        if not isinstance(sol, dict):
            continue
        pricing = sol.get("pricing")
        if not isinstance(pricing, dict):
            continue
        total = pricing.get("total")
        if not isinstance(total, dict):
            continue
        price = total.get("price")
        if not isinstance(price, dict):
            continue

        try:
            amount = float(price.get("amount"))
        except Exception:  # noqa: BLE001
            continue

        currency = str(price.get("currency") or currency)
        total_amount += amount

    return total_amount, currency


def _attach_seats_to_cart(shopping_cart: dict[str, Any], seat_selections: list[dict[str, Any]]) -> None:
    """Attach seat selections in multiple conventional locations."""

    shopping_cart["seatSelections"] = seat_selections
    order = shopping_cart.get("order")
    if isinstance(order, dict):
        order["seatSelections"] = seat_selections
        airs = order.get("airs")
        if isinstance(airs, list) and airs:
            a0 = airs[0]
            if isinstance(a0, dict):
                a0["seatSelections"] = seat_selections
                anc = a0.get("ancillaries")
                if not isinstance(anc, dict):
                    anc = {}
                    a0["ancillaries"] = anc
                anc["seatSelections"] = seat_selections


def _update_store_seats(
    store: MockStateStore,
    *,
    ctx: RequestContext,
    order_id: str,
    cart_id: str,
    air_id: str,
    new_selections: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Persist selection changes; returns (updated, warnings)."""

    warnings: list[dict[str, Any]] = []

    store.ensure_order(order_id, ctx)
    store.ensure_shopping_cart(order_id, cart_id)
    air_state, _ = store.ensure_air(order_id, cart_id, air_id)

    existing = air_state.ancillaries.get("seatSelections")
    if not isinstance(existing, list):
        existing = []

    existing_norm = [_safe_json(x) for x in existing]

    by_psg_seg: dict[tuple[str, str], dict[str, Any]] = {}
    by_seg_seat: dict[tuple[str, str], dict[str, Any]] = {}

    for s in existing_norm:
        pid = str(s.get("passengerId") or "").strip()
        sid = str(s.get("segmentId") or "").strip()
        rn = str(s.get("rowNumber") or "").strip()
        sn = str(s.get("seatNumber") or "").strip().upper()
        if not pid or not sid:
            continue
        by_psg_seg[(pid, sid)] = s
        if rn and sn:
            by_seg_seat[(sid, f"{rn}{sn}")] = s

    for s in new_selections:
        pid = str(s.get("passengerId") or "").strip()
        sid = str(s.get("segmentId") or "").strip()
        rn = str(s.get("rowNumber") or "").strip()
        sn = str(s.get("seatNumber") or "").strip().upper()

        if not pid or not sid or not rn or not sn:
            warnings.append(
                {
                    "code": "SEAT_SELECTION_INVALID",
                    "message": "Seat selection entry is missing required fields; ignored.",
                    "details": {"passengerId": pid, "segmentId": sid, "rowNumber": rn, "seatNumber": sn},
                }
            )
            continue

        seat_key = f"{rn}{sn}"
        other = by_seg_seat.get((sid, seat_key))
        if other is not None and str(other.get("passengerId") or "") != pid:
            other_pid = str(other.get("passengerId") or "")
            warnings.append(
                {
                    "code": "SEAT_REASSIGNED",
                    "message": "Seat was previously assigned to another passenger; assignment moved.",
                    "details": {"segmentId": sid, "seat": seat_key, "fromPassengerId": other_pid, "toPassengerId": pid},
                }
            )
            by_psg_seg.pop((other_pid, sid), None)

        sel_obj = {
            "passengerId": pid,
            "segmentId": sid,
            "rowNumber": rn,
            "seatNumber": sn,
            "priorityMember": s.get("priorityMember"),
            "priorityClassicMember": s.get("priorityClassicMember"),
            "specialAssistance": s.get("specialAssistance"),
            "redemption": s.get("redemption"),
            "usePoints": s.get("usePoints"),
            "smiFree": s.get("smiFree"),
        }

        by_psg_seg[(pid, sid)] = sel_obj
        by_seg_seat[(sid, seat_key)] = sel_obj

    updated = list(by_psg_seg.values())
    air_state.ancillaries["seatSelections"] = updated
    air_state.updated_at = now_utc_iso()
    air_state.revision = store.touch()
    return updated, warnings


def _delete_store_seats(
    store: MockStateStore,
    *,
    ctx: RequestContext,
    order_id: str,
    cart_id: str,
    air_id: str,
    segment_id: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []

    store.ensure_order(order_id, ctx)
    store.ensure_shopping_cart(order_id, cart_id)
    air_state, _ = store.ensure_air(order_id, cart_id, air_id)

    existing = air_state.ancillaries.get("seatSelections")
    if not isinstance(existing, list):
        existing = []

    existing_norm = [_safe_json(x) for x in existing]

    if segment_id:
        seg = str(segment_id).strip()
        kept = [s for s in existing_norm if str(s.get("segmentId") or "").strip() != seg]
    else:
        seg = None
        kept = []

    air_state.ancillaries["seatSelections"] = kept
    air_state.updated_at = now_utc_iso()
    air_state.revision = store.touch()

    warnings.append(
        {
            "code": "SEAT_SELECTION_CLEARED",
            "message": "Seat selections were cleared in the mock.",
            "details": {"segmentId": seg, "airId": air_id},
        }
    )

    return kept, warnings


def _reprice_cart(
    store: MockStateStore,
    *,
    ctx: RequestContext,
    order_id: str,
    cart_id: str,
    air_id: str,
) -> tuple[dict[str, Any], str]:
    """Recompute cart pricing based on flights + seat selections."""

    cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)
    order_state, _ = store.ensure_order(order_id, ctx)

    flights_total = 0.0
    currency = order_state.currency or "USD"
    if cart_state.flights_search:
        flights_total, currency = _compute_flights_total(_safe_json(cart_state.flights_search))

    air_state, _ = store.ensure_air(order_id, cart_id, air_id)
    seat_total = 0.0
    if isinstance(air_state.ancillaries.get("seatSelections"), list):
        for s in air_state.ancillaries.get("seatSelections"):
            sd = _safe_json(s)
            seat_total += _seat_price(str(sd.get("rowNumber") or ""), str(sd.get("seatNumber") or ""))

    total = flights_total + seat_total

    cart_state.pricing = _make_pricing(total, currency)
    cart_state.updated_at = now_utc_iso()
    cart_state.revision = store.touch()

    order_state.currency = currency
    order_state.updated_at = now_utc_iso()
    order_state.revision = store.touch()

    return cart_state.pricing, currency


async def put_or_delete_seats(request: Request) -> JSONResponse:
    """PUT/DELETE seats endpoint."""

    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()
    air_id = str(request.path_params.get("airId") or "").strip()

    payload = ok()
    with_context_warnings(payload, context_warnings=ctx.warnings)

    if store is None:
        payload["warnings"].append(
            {
                "code": "STATE_STORE_MISSING",
                "message": "State store is not available; seat selections were not persisted.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    store.ensure_from_request(ctx=ctx, path_params=request.path_params)

    warnings: list[dict[str, Any]] = []

    if request.method.upper() == "DELETE":
        segment_id = request.query_params.get("segmentId")
        seat_selections, w = _delete_store_seats(
            store,
            ctx=ctx,
            order_id=order_id,
            cart_id=cart_id,
            air_id=air_id,
            segment_id=segment_id,
        )
        warnings.extend(w)
    else:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}

        seat_selections_req = _extract_seat_selections(_safe_json(body))
        seat_selections, w = _update_store_seats(
            store,
            ctx=ctx,
            order_id=order_id,
            cart_id=cart_id,
            air_id=air_id,
            new_selections=seat_selections_req,
        )
        warnings.extend(w)

    pricing, currency = _reprice_cart(store, ctx=ctx, order_id=order_id, cart_id=cart_id, air_id=air_id)

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = "SEATS"
    shopping_cart["pricing"] = pricing
    _attach_seats_to_cart(shopping_cart, seat_selections)

    payload.update(
        {
            "retrieve": {"shoppingCart": True, "ancillariesPricing": True},
            "shoppingCart": shopping_cart,
        }
    )
    for w in warnings:
        payload["warnings"].append(w)

    payload["mock"] = {
        "kind": "SeatSelection",
        "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        "requestMethod": request.method,
        "seatsCount": len(seat_selections),

    }
    return JSONResponse(payload, status_code=200)
