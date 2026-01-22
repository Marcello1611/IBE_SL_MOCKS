"""Baggage selection handlers (Step 8).

Implements stateful selection of up to 2 bag items per passenger+route, with
"happy-hour" pricing:
- first bag: discounted
- second bag: regular

Covered endpoints:
- PUT /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/baggage
- PUT /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/ancillaries/bags
- DELETE /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/bags?routeId=...

Goal: UI can select 2 bags and see different prices without crashes.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ..headers import RequestContext, build_request_context
from ..responses import ok, with_context_warnings
from ..debug import debug_enabled
from ..state import MockStateStore
from ..versioning import now_utc_iso, stable_id

from .flights_search import _build_shopping_cart_payload, _safe_json
from .seats import _reprice_cart


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _extract_baggage_selections(payload: Any) -> list[dict[str, Any]]:
    """Extract BaggageSelection-like objects from request JSON."""

    if not isinstance(payload, dict):
        return []

    raw = payload.get("baggageSelections")
    if isinstance(raw, dict):
        raw_list = [raw]
    else:
        raw_list = _safe_list(raw)

    out: list[dict[str, Any]] = []
    for item in raw_list:
        d = _safe_json(item)
        if not d:
            continue
        baggage_ids = d.get("baggageIds")
        if isinstance(baggage_ids, list):
            ids = [str(x).strip() for x in baggage_ids if str(x).strip()]
        else:
            ids = []
        out.append(
            {
                "passengerId": str(d.get("passengerId") or "").strip(),
                "routeId": str(d.get("routeId") or d.get("segmentId") or "").strip(),
                "baggageIds": ids,
                "redemption": d.get("redemption"),
                "usePoints": d.get("usePoints"),
                "equipmentType": d.get("equipmentType"),
            }
        )
    return out


def _make_bag_item(
    *,
    passenger_id: str,
    route_id: str,
    baggage_id: str,
    idx: int,
    currency: str,
) -> dict[str, Any]:
    # Happy hour pricing: first discounted, second regular.
    discounted = idx == 0
    amount = 15.0 if discounted else 30.0

    return {
        "id": stable_id("bag", f"{passenger_id}|{route_id}|{baggage_id}|{idx}", length=16),
        "passengerId": passenger_id,
        "routeId": route_id,
        "baggageId": baggage_id,
        "discounted": discounted,
        "amount": amount,
        "currency": currency,
        # Provide a few extra fields that UIs often expect.
        "code": "BAG_DISCOUNTED" if discounted else "BAG_REGULAR",
        "name": "1 bag discounted" if discounted else "1 bag",
        "createdAt": now_utc_iso(),
    }


def _apply_baggage(
    store: MockStateStore,
    *,
    ctx: RequestContext,
    order_id: str,
    cart_id: str,
    air_id: str,
    baggage_selections: list[dict[str, Any]],
    currency: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Persist baggage selections and items; returns (selections, items, warnings)."""

    warnings: list[dict[str, Any]] = []

    store.ensure_order(order_id, ctx)
    store.ensure_shopping_cart(order_id, cart_id)
    air_state, _ = store.ensure_air(order_id, cart_id, air_id)

    normalized: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    # Limit: up to 2 bag items per passenger+routeId (tolerant mapping).
    for sel in baggage_selections:
        pid = str(sel.get("passengerId") or "").strip()
        rid = str(sel.get("routeId") or "").strip() or "route-0"
        ids = sel.get("baggageIds") or []
        if not pid:
            warnings.append(
                {
                    "code": "BAG_SELECTION_INVALID",
                    "message": "Missing passengerId in baggage selection; ignored.",
                    "details": {"routeId": rid},
                }
            )
            continue

        ids2 = [str(x).strip() for x in ids if str(x).strip()][:2]
        normalized.append({"passengerId": pid, "routeId": rid, "baggageIds": ids2})

        for idx, bid in enumerate(ids2):
            items.append(_make_bag_item(passenger_id=pid, route_id=rid, baggage_id=bid, idx=idx, currency=currency))

        if len(ids) > 2:
            warnings.append(
                {
                    "code": "BAG_LIMIT_APPLIED",
                    "message": "Mock limits baggage to 2 items per passenger and route.",
                    "details": {"passengerId": pid, "routeId": rid, "requested": len(ids), "kept": 2},
                }
            )

    air_state.ancillaries["baggageSelections"] = normalized
    air_state.ancillaries["baggageItems"] = items
    air_state.updated_at = now_utc_iso()
    air_state.revision = store.touch()

    # Also keep a lightweight pricing block that many UIs can display.
    air_state.ancillaries["baggagePricing"] = {
        "currency": currency,
        "items": items,
        "total": {"amount": round(sum(float(it.get("amount", 0.0)) for it in items), 2), "currency": currency},
    }

    return normalized, items, warnings


def _attach_baggage_to_cart(shopping_cart: dict[str, Any], selections: list[dict[str, Any]], items: list[dict[str, Any]]) -> None:
    shopping_cart["baggageSelections"] = selections
    shopping_cart["baggageItems"] = items

    order = shopping_cart.get("order")
    if isinstance(order, dict):
        order["baggageSelections"] = selections
        airs = order.get("airs")
        if isinstance(airs, list) and airs:
            a0 = airs[0]
            if isinstance(a0, dict):
                a0["baggageSelections"] = selections
                anc = a0.get("ancillaries")
                if not isinstance(anc, dict):
                    anc = {}
                    a0["ancillaries"] = anc
                anc["baggageSelections"] = selections
                anc["baggageItems"] = items
                anc["baggagePricing"] = {
                    "currency": items[0]["currency"] if items else shopping_cart.get("currentCurrency") or "USD",
                    "items": items,
                }


async def put_select_baggage(request: Request) -> JSONResponse:
    """PUT /.../baggage"""

    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()
    air_id = str(request.path_params.get("airId") or "").strip()

    payload = ok()
    with_context_warnings(payload, context_warnings=ctx.warnings)

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    req = _safe_json(body)
    baggage_selections = _extract_baggage_selections(req)

    if store is None:
        payload["warnings"].append(
            {
                "code": "STATE_STORE_MISSING",
                "message": "State store is not available; baggage selections were not persisted.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    store.ensure_from_request(ctx=ctx, path_params=request.path_params)
    order_state, _ = store.ensure_order(order_id, ctx)
    currency = order_state.currency or "USD"

    selections, items, warnings = _apply_baggage(
        store,
        ctx=ctx,
        order_id=order_id,
        cart_id=cart_id,
        air_id=air_id,
        baggage_selections=baggage_selections,
        currency=currency,
    )

    pricing, currency = _reprice_cart(store, ctx=ctx, order_id=order_id, cart_id=cart_id, air_id=air_id)

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = "BAGS"
    shopping_cart["pricing"] = pricing
    _attach_baggage_to_cart(shopping_cart, selections, items)

    payload.update({"retrieve": {"shoppingCart": True, "ancillariesPricing": True}, "shoppingCart": shopping_cart})
    for w in warnings:
        payload["warnings"].append(w)

    mock_meta = {
        "kind": "BaggageSelection",
        "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        "bagsCount": len(items),
    }
    if debug_enabled():
        payload["mock"] = mock_meta
    return JSONResponse(payload, status_code=200)


async def put_update_bags(request: Request) -> JSONResponse:
    """PUT /.../ancillaries/bags"""

    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()
    air_id = str(request.path_params.get("airId") or "").strip()

    payload = ok()
    with_context_warnings(payload, context_warnings=ctx.warnings)

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    req = _safe_json(body)
    baggage_selections = _extract_baggage_selections(req)

    if store is None:
        payload["warnings"].append(
            {
                "code": "STATE_STORE_MISSING",
                "message": "State store is not available; ancillaries bags update was not persisted.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    store.ensure_from_request(ctx=ctx, path_params=request.path_params)
    order_state, _ = store.ensure_order(order_id, ctx)
    currency = order_state.currency or "USD"

    selections, items, warnings = _apply_baggage(
        store,
        ctx=ctx,
        order_id=order_id,
        cart_id=cart_id,
        air_id=air_id,
        baggage_selections=baggage_selections,
        currency=currency,
    )

    pricing, currency = _reprice_cart(store, ctx=ctx, order_id=order_id, cart_id=cart_id, air_id=air_id)

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = "BAGS"
    shopping_cart["pricing"] = pricing
    _attach_baggage_to_cart(shopping_cart, selections, items)

    payload.update({"retrieve": {"shoppingCart": True, "ancillariesPricing": True}, "shoppingCart": shopping_cart})
    for w in warnings:
        payload["warnings"].append(w)

    mock_meta = {
        "kind": "AncillariesBagsUpdate",
        "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        "bagsCount": len(items),
    }
    if debug_enabled():
        payload["mock"] = mock_meta
    return JSONResponse(payload, status_code=200)


async def delete_shopping_cart_bags(request: Request) -> JSONResponse:
    """DELETE /.../bags?routeId=..."""

    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()
    air_id = str(request.path_params.get("airId") or "").strip()
    route_id = str(request.query_params.get("routeId") or "").strip()

    payload = ok()
    with_context_warnings(payload, context_warnings=ctx.warnings)

    if store is None:
        payload["warnings"].append(
            {
                "code": "STATE_STORE_MISSING",
                "message": "State store is not available; bags delete was not persisted.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    store.ensure_from_request(ctx=ctx, path_params=request.path_params)
    store.ensure_order(order_id, ctx)
    store.ensure_shopping_cart(order_id, cart_id)
    air_state, _ = store.ensure_air(order_id, cart_id, air_id)

    selections = air_state.ancillaries.get("baggageSelections")
    if not isinstance(selections, list):
        selections = []
    items = air_state.ancillaries.get("baggageItems")
    if not isinstance(items, list):
        items = []

    if route_id:
        selections2 = []
        for s in selections:
            sd = _safe_json(s)
            if str(sd.get("routeId") or "").strip() != route_id:
                selections2.append(sd)
        items2 = []
        for it in items:
            itd = _safe_json(it)
            if str(itd.get("routeId") or "").strip() != route_id:
                items2.append(itd)
        selections = selections2
        items = items2
    else:
        selections = []
        items = []

    air_state.ancillaries["baggageSelections"] = selections
    air_state.ancillaries["baggageItems"] = items
    air_state.updated_at = now_utc_iso()
    air_state.revision = store.touch()

    pricing, currency = _reprice_cart(store, ctx=ctx, order_id=order_id, cart_id=cart_id, air_id=air_id)
    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = "BAGS"
    shopping_cart["pricing"] = pricing
    _attach_baggage_to_cart(shopping_cart, selections, items)

    payload.update({"retrieve": {"shoppingCart": True, "ancillariesPricing": True}, "shoppingCart": shopping_cart})
    payload["warnings"].append(
        {"code": "BAGS_CLEARED", "message": "Bags cleared in the mock.", "details": {"routeId": route_id or None}}
    )
    mock_meta = {
        "kind": "BaggageDelete",
        "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        "routeId": route_id or None,
        "bagsCount": len(items),
    }
    if debug_enabled():
        payload["mock"] = mock_meta
    return JSONResponse(payload, status_code=200)
