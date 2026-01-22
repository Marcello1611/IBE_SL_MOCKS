"""Bookings handlers.

Implements:
- POST /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/bookings

The real backend produces richer booking DTOs. The mock focuses on:
- stable BaseResponse envelope
- returning ShoppingCart-shaped payload with a reasonable next step
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ..debug import debug_enabled
from ..headers import RequestContext, build_request_context
from ..responses import ok, with_context_warnings
from ..state import MockStateStore
from ..versioning import stable_id, now_utc_iso

from .flights_search import _build_shopping_cart_payload, _make_pricing, _safe_json


def _resolve_air_id(store: MockStateStore, ctx: RequestContext, order_id: str, cart_id: str) -> str:
    order_state, _ = store.ensure_order(order_id, ctx)
    if order_state.added_air_id:
        return order_state.added_air_id

    cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)
    if cart_state.selected_airs:
        return cart_state.selected_airs[0]

    air_id = stable_id("air", f"{order_id}|{cart_id}", length=16)
    store.ensure_air(order_id, cart_id, air_id)
    cart_state.selected_airs.append(air_id)
    order_state.added_air_id = air_id
    store.touch()
    return air_id


def _attach_existing_ancillaries(store: MockStateStore, *, order_id: str, cart_id: str, air_id: str, shopping_cart: dict[str, Any]) -> None:
    air_state, _ = store.ensure_air(order_id, cart_id, air_id)
    seats = air_state.ancillaries.get("seatSelections")
    bags = air_state.ancillaries.get("baggageSelections")
    items = air_state.ancillaries.get("baggageItems")
    meals = air_state.ancillaries.get("mealSelections")

    if isinstance(seats, list):
        shopping_cart["seatSelections"] = [_safe_json(x) for x in seats]
    if isinstance(bags, list):
        shopping_cart["baggageSelections"] = [_safe_json(x) for x in bags]
    if isinstance(items, list):
        shopping_cart["baggageItems"] = [_safe_json(x) for x in items]
    if isinstance(meals, list):
        shopping_cart["mealSelections"] = [_safe_json(x) for x in meals]

    order = shopping_cart.get("order")
    if isinstance(order, dict):
        airs = order.get("airs")
        if isinstance(airs, list) and airs:
            a0 = airs[0]
            if isinstance(a0, dict):
                anc = a0.get("ancillaries")
                if not isinstance(anc, dict):
                    anc = {}
                    a0["ancillaries"] = anc
                for k in ("seatSelections", "baggageSelections", "baggageItems", "mealSelections"):
                    if k in shopping_cart:
                        anc[k] = shopping_cart[k]


async def post_bookings(request: Request) -> JSONResponse:
    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()

    payload = ok()
    with_context_warnings(payload, context_warnings=ctx.warnings)

    if store is None:
        payload["warnings"].append(
            {
                "code": "STATE_STORE_MISSING",
                "message": "State store is not available; booking was not persisted.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    # Best-effort body parse; not used yet.
    try:
        _ = await request.json()
    except Exception:  # noqa: BLE001
        pass

    store.ensure_order(order_id, ctx)
    cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)
    air_id = _resolve_air_id(store, ctx, order_id, cart_id)

    # Determine currency/pricing based on last computed cart pricing.
    currency = "USD"
    pricing = None
    if isinstance(cart_state.pricing, dict) and cart_state.pricing:
        pricing = cart_state.pricing
        # Try to extract currency from pricing.total.price.currency
        try:
            currency = str(pricing.get("total", {}).get("price", {}).get("currency") or currency)
        except Exception:  # noqa: BLE001
            currency = currency
    if pricing is None:
        pricing = _make_pricing(0.0, currency)

    # Mark cart/order as progressed.
    cart_state.updated_at = now_utc_iso()
    cart_state.revision = store.touch()

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = "PAYMENT"
    shopping_cart["pricing"] = pricing
    _attach_existing_ancillaries(store, order_id=order_id, cart_id=cart_id, air_id=air_id, shopping_cart=shopping_cart)

    payload.update(
        {
            "retrieve": {"shoppingCart": True, "ancillariesPricing": True},
            "shoppingCart": shopping_cart,
        }
    )

    if debug_enabled():
        payload["mock"] = {
            "kind": "BookingsCreate",
            "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        }

    return JSONResponse(payload, status_code=200)
