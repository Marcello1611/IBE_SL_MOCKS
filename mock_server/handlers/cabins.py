"""Cabins (seat map) handlers (Step 6).

Goal
----
Return a *full aircraft seat map* so UI can render complete cabin layouts.

Endpoints (FlightsRest)
----------------------
- GET /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/cabins
- GET /api/v1/shoppingCarts/{shoppingCartId}/airs/{airId}/cabins
- GET /api/v1/orders/{orderId}/airs/{airId}/cabins
- GET /api/v1/orders/{orderId}/airs/{airId}/segments/{segmentId}/passengers/{passengerId}/cabins

Contract
--------
CabinsSearchResponse:
  - BaseResponse fields
  - cabins: List<SeatCabin>
  - selectPriorityMember: boolean

SeatCabin:
  - cabinType: str
  - segment: Segment
  - rows: List<SeatRow>
  - columnNamesRow: str
  - priceGroups: Map[str, Pricing]

Implementation notes
--------------------
- Keep responses deterministic based on (conversationId, airId, segmentId).
- Provide Boeing 787-9-like economy layout (rows 15-54) with columns A B C D F G H J K.
- Provide Premium and Business cabins with simplified layouts (sufficient for tabs).
- Never raise: always return HTTP 200 with BaseResponse-shaped JSON.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from fastapi import Request
from fastapi.responses import JSONResponse

from ..headers import RequestContext, build_request_context
from ..responses import ok, with_context_warnings
from ..state import MockStateStore
from ..versioning import stable_id


def _safe_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _now_local_iso() -> str:
    # Segment dates in generated flights_search are LocalDateTime w/o timezone suffix.
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _plain_price(amount: float, currency: str) -> dict[str, Any]:
    return {"amount": round(float(amount), 2), "currency": currency}


def _price(amount: float, currency: str) -> dict[str, Any]:
    # Price model: include both `price` and `salePrice` to satisfy various consumers.
    pp = _plain_price(amount, currency)
    return {
        "price": pp,
        "salePrice": pp,
        "redemption": None,
        "residualPrice": None,
        "discountPercent": None,
        "redemptionDiscountPercent": None,
        "conversionRate": None,
        "points": None,
        "milesConversionRank": None,
    }


def _pricing(total_amount: float, currency: str) -> dict[str, Any]:
    return {
        "total": _price(total_amount, currency),
        "base": None,
        "taxes": None,
        "fees": None,
        "bankFee": None,
        "agentFee": None,
        "agentCommission": None,
        "agentFixCommission": None,
        "equivAgentTst": None,
        "discount": None,
        "discounts": None,
        "penalty": None,
        "taxBreakdowns": [],
        "supplierPrice": None,
        "reissuePrice": None,
        "charge": None,
        "reissueFareBalance": None,
        "reissueTaxBalance": None,
        "equiv": None,
        "additionalCollectionPrice": None,
        "profiPointLimit": None,
    }


def _airline(code: str, *, name: str = "Mock Airlines") -> dict[str, Any]:
    return {"code": code, "displayCode": code, "name": name}


def _airport(code: str, *, terminal: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": code}
    if terminal is not None:
        out["terminal"] = terminal
    return out


def _segment_from_search(store: MockStateStore, *, order_id: str, cart_id: str) -> dict[str, Any] | None:
    """Try to obtain a Segment from FlightsSearch state.

    We prefer returning the same segment IDs as flights_search (used later for seats).
    """

    cart_state = store.shopping_carts.get(cart_id)
    if cart_state is None:
        return None

    search = _safe_json(cart_state.flights_search)
    option_sets = search.get("optionSets")
    if not isinstance(option_sets, list) or not option_sets:
        return None

    # Pick selected option (or first) and then the first segment of the first route.
    os0 = _safe_json(option_sets[0])
    option_id = (os0.get("selection") or {}).get("optionId") if isinstance(os0.get("selection"), dict) else None

    options = os0.get("options")
    if not isinstance(options, list) or not options:
        return None

    opt0: dict[str, Any] | None = None
    for opt in options:
        oo = _safe_json(opt)
        if option_id and oo.get("id") == option_id:
            opt0 = oo
            break
    if opt0 is None:
        opt0 = _safe_json(options[0])

    routes = opt0.get("routes")
    if not isinstance(routes, list) or not routes:
        return None

    r0 = _safe_json(routes[0])
    segs = r0.get("segments")
    if not isinstance(segs, list) or not segs:
        return None

    # flights_search segment already has many fields; keep it as-is.
    return _safe_json(segs[0])


def _stable_bool(seed: str, *, numerator: int, denominator: int) -> bool:
    # Deterministic pseudo-random bool: based on sha1 prefix.
    sid = stable_id("h", seed, length=8)
    n = int(sid.split("-", 1)[1], 16)
    return (n % denominator) < numerator


def _iter_columns_with_aisles(columns: list[str]) -> list[str]:
    """Economy 787-like layout.

    We keep 9 seat columns and add two "gaps" as absent places.
    This yields 11 positions per row, matching the visual map.
    """

    if len(columns) == 9:
        # A B C  _  D F G  _  H J K
        return columns[:3] + ["_"] + columns[3:6] + ["_"] + columns[6:]
    return columns


def _place(
    *,
    row: str,
    col: str,
    currency: str,
    available: bool,
    seat_type: str,
    emergency: bool,
) -> dict[str, Any]:
    """Build SeatPlace JSON."""

    if col == "_":
        return {
            "number": None,
            "available": False,
            "absent": True,
            "enableAutoSelection": False,
            "availablePassengers": [],
            "passengerSeatRestriction": {},
            "infantAllowed": None,
            "infantNotAvailable": None,
            "petAllowed": False,
            "childAllowed": None,
            "notRecline": False,
            "rightAisle": None,
            "exists": False,
            "window": None,
            "middle": None,
            "aisle": None,
            "commonRestricted": None,
            "notRecommended": None,
            "withoutWindow": None,
            "seat": None,
            "emergency": False,
        }

    # Seat category + pricing.
    if seat_type == "XL":
        category = "comfortable"
        extra_space = True
        desc = "Leg space"
        amount = 25.0
        price_group = "XL"
        chargeable = True
    elif seat_type == "EXIT":
        category = "preferential"
        extra_space = False
        desc = "Exit row"
        amount = 30.0
        price_group = "EXIT"
        chargeable = True
    else:
        category = "standard"
        extra_space = False
        desc = "Standard seat"
        amount = 0.0
        price_group = "STD"
        chargeable = False

    # Seat position flags.
    window = col in {"A", "K"}
    aisle = col in {"C", "D", "G", "H"}
    middle = (not window) and (not aisle)

    seat_obj = {
        "pricing": _pricing(amount, currency),
        "analyticsParams": None,
        "row": row,
        "number": col,
        "description": desc,
        "extraSpace": extra_space,
        "category": category,
        "priceGroup": price_group,
        "hideDiscount": False,
        "hideRedemptionDiscount": False,
        "frontCabin": None,
        "chargeable": chargeable,
        "priceGroupByPassengerId": None,
    }

    return {
        "number": col,
        "available": bool(available),
        "absent": False,
        "enableAutoSelection": True,
        "availablePassengers": [],
        "passengerSeatRestriction": {},
        "infantAllowed": None,
        "infantNotAvailable": None,
        "petAllowed": False,
        "childAllowed": None,
        "notRecline": False,
        "rightAisle": None,
        "exists": True,
        "window": window,
        "middle": middle,
        "aisle": aisle,
        "commonRestricted": None,
        "notRecommended": None,
        "withoutWindow": None,
        "seat": seat_obj,
        "emergency": bool(emergency),
    }


def _row(
    *,
    row_number: int,
    cabin_class: str,
    columns: list[str],
    currency: str,
    seed: str,
    xl_rows: set[int],
    exit_rows: set[int],
) -> dict[str, Any]:
    row_str = str(row_number)
    is_exit = row_number in exit_rows

    cols = _iter_columns_with_aisles(columns)
    places: list[dict[str, Any]] = []

    for col in cols:
        if col == "_":
            places.append(_place(row=row_str, col=col, currency=currency, available=False, seat_type="STD", emergency=False))
            continue

        # A small deterministic share of seats is unavailable.
        occupied = _stable_bool(f"{seed}|{row_str}{col}", numerator=2, denominator=11)
        available = not occupied

        # Tagging.
        seat_type = "STD"
        emergency = False

        if is_exit and col in {"A", "B", "C", "H", "J", "K"}:
            seat_type = "EXIT"
            emergency = True
        if row_number in xl_rows and col in {"D", "F", "G"}:
            seat_type = "XL"

        places.append(
            _place(
                row=row_str,
                col=col,
                currency=currency,
                available=available,
                seat_type=seat_type,
                emergency=emergency,
            )
        )

    return {
        "cabinClass": cabin_class,
        "numberOfSeats": str(len([c for c in cols if c != "_"])),
        "number": row_str,
        "places": places,
        "exit": bool(is_exit),
        "wing": None,
        "disclaimer": None,
        "extraSeatPairs": [],
    }


def _cabin(
    *,
    cabin_type: str,
    segment: dict[str, Any],
    currency: str,
    seed: str,
) -> dict[str, Any]:
    if cabin_type == "BUSINESS":
        columns = ["A", "D", "F", "K"]
        row_range = range(1, 6)
        xl_rows: set[int] = set()
        exit_rows: set[int] = set()
        cabin_class = "BUSINESS"
    elif cabin_type == "PREMIUM":
        columns = ["A", "B", "D", "E", "F", "J", "K"]
        row_range = range(6, 15)
        xl_rows = {10}
        exit_rows = set()
        cabin_class = "PREMIUM"
    else:
        # ECONOMY 787-9 like: 15-54, 3-3-3
        columns = ["A", "B", "C", "D", "F", "G", "H", "J", "K"]
        row_range = range(15, 55)
        xl_rows = {15, 40}
        exit_rows = {15, 40}
        cabin_class = "ECONOMY"

    rows = [
        _row(
            row_number=r,
            cabin_class=cabin_class,
            columns=columns,
            currency=currency,
            seed=seed,
            xl_rows=xl_rows,
            exit_rows=exit_rows,
        )
        for r in row_range
    ]

    # Price groups allow the UI to show a legend.
    price_groups = {
        "STD": _pricing(0.0, currency),
        "XL": _pricing(25.0, currency),
        "EXIT": _pricing(30.0, currency),
    }

    # Provide a header row string; consumers might use it directly.
    if cabin_type == "ECONOMY":
        column_names = "A B C   D F G   H J K"
    elif cabin_type == "PREMIUM":
        column_names = "A B   D E F   J K"
    else:
        column_names = "A   D F   K"

    return {
        "cabinType": cabin_type,
        "segment": segment,
        "rows": rows,
        "columnNamesRow": column_names,
        "passengersAmount": None,
        "passengerBreakdowns": [],
        "priceGroups": price_groups,
    }


def _segments_for_response(
    store: MockStateStore,
    *,
    ctx: RequestContext,
    order_id: str,
    cart_id: str | None,
    air_id: str,
    segment_id_hint: str | None,
) -> list[dict[str, Any]]:
    if cart_id:
        seg = _segment_from_search(store, order_id=order_id, cart_id=cart_id)
        if seg is not None:
            if segment_id_hint and seg.get("id") and str(seg.get("id")) != segment_id_hint:
                # Caller hints segmentId; still return the generated segment (UI typically ignores mismatch).
                pass
            return [seg]

    # Fallback: minimal Segment.
    seg_id = segment_id_hint or stable_id("seg", f"{ctx.conversation_id}|{air_id}", length=16)
    return [
        {
            "id": seg_id,
            "departureAirport": _airport("AAA"),
            "arrivalAirport": _airport("BBB"),
            "departureDate": _now_local_iso(),
            "arrivalDate": _now_local_iso(),
            "departureTimeZone": "UTC",
            "arrivalTimeZone": "UTC",
            "duration": {"amount": 120, "unit": "minutes"},
            "marketingAirline": _airline("MO"),
            "operatingAirline": _airline("MO"),
            "displayAirlineCode": "MO",
            "statusByCoupons": "OK",
            "actual": False,
        }
    ]


async def _cabins_response(
    request: Request,
    *,
    order_id: str | None,
    cart_id: str | None,
    air_id: str,
    segment_id_hint: str | None = None,
) -> JSONResponse:
    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))

    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    currency = "USD"

    warnings: list[dict[str, Any]] = []
    if store is not None:
        try:
            warnings.extend(store.ensure_from_request(ctx=ctx, path_params=request.path_params))
            if order_id:
                order_state, _ = store.ensure_order(order_id, ctx)
                currency = order_state.currency or currency
        except Exception:  # noqa: BLE001
            warnings.append(
                {
                    "code": "STATE_STORE_WARNING",
                    "message": "State store failed to process cabins request; continuing with generated seat map.",
                    "details": {"path": request.url.path},
                }
            )

    # Determine segment(s).
    segments: list[dict[str, Any]]
    if store is not None:
        segments = _segments_for_response(
            store,
            ctx=ctx,
            order_id=order_id or "",
            cart_id=cart_id,
            air_id=air_id,
            segment_id_hint=segment_id_hint,
        )
    else:
        segments = _segments_for_response(
            MockStateStore(),  # isolated fallback
            ctx=ctx,
            order_id=order_id or "",
            cart_id=None,
            air_id=air_id,
            segment_id_hint=segment_id_hint,
        )

    cabins: list[dict[str, Any]] = []
    for seg in segments:
        seg_id = str(seg.get("id") or "")
        seed = f"{ctx.conversation_id}|{air_id}|{seg_id}"
        cabins.append(_cabin(cabin_type="ECONOMY", segment=seg, currency=currency, seed=seed))
        cabins.append(_cabin(cabin_type="PREMIUM", segment=seg, currency=currency, seed=seed + "|P"))
        cabins.append(_cabin(cabin_type="BUSINESS", segment=seg, currency=currency, seed=seed + "|B"))

    payload = ok(
        {
            "cabins": cabins,
            "selectPriorityMember": False,
        }
    )
    with_context_warnings(payload, context_warnings=ctx.warnings)
    for w in warnings:
        payload["warnings"].append(w)

    payload["mock"] = {
        "kind": "CabinsSearchResponse",
        "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        "segments": [s.get("id") for s in segments],
    }

    return JSONResponse(payload, status_code=200)


async def get_cabins_cart(request: Request) -> JSONResponse:
    return await _cabins_response(
        request,
        order_id=str(request.path_params.get("orderId") or "").strip() or None,
        cart_id=str(request.path_params.get("shoppingCartId") or "").strip() or None,
        air_id=str(request.path_params.get("airId") or "").strip(),
    )


async def get_cabins_cart_short(request: Request) -> JSONResponse:
    # Some clients omit orderId.
    return await _cabins_response(
        request,
        order_id=None,
        cart_id=str(request.path_params.get("shoppingCartId") or "").strip() or None,
        air_id=str(request.path_params.get("airId") or "").strip(),
    )


async def get_cabins_postsell(request: Request) -> JSONResponse:
    return await _cabins_response(
        request,
        order_id=str(request.path_params.get("orderId") or "").strip() or None,
        cart_id=None,
        air_id=str(request.path_params.get("airId") or "").strip(),
    )


async def get_cabins_v2(request: Request) -> JSONResponse:
    return await _cabins_response(
        request,
        order_id=str(request.path_params.get("orderId") or "").strip() or None,
        cart_id=None,
        air_id=str(request.path_params.get("airId") or "").strip(),
        segment_id_hint=str(request.path_params.get("segmentId") or "").strip() or None,
    )
