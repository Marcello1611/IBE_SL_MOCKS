"""Meals and drinks ancillaries (Step 9).

Implements stateful meal/drink selection bound to passenger+segment.
Drinks are represented as meal products with category=DRINK.

Endpoints:
- PUT /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/meals
  (FlightsRest.selectMeals)  body: MealsSelectionRequest { mealSelection: MealSelection }
- PUT /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/ancillaries/meals
  (FlightsRest.updateMeals)  body: AncillariesUpdateRequest { mealSelections: [MealSelection] }
- DELETE /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/meals?segmentId=...
  (FlightsRest.deleteShoppingCartMeals)

Mock goals:
- Provide stable catalog: "gourmet meal" + drinks (incl. champagne).
- Accept unknown meal IDs without failing.
- Reprice the cart (total includes meals/drinks fees).
- Never crash UI: always return BaseResponse envelope and shoppingCart.
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

from .flights_search import _build_shopping_cart_payload, _safe_json, _safe_list
from .seats import _reprice_cart


def _meal_catalog(currency: str) -> list[dict[str, Any]]:
    # Stable IDs; UI can use them directly in selection requests.
    def item(*, item_id: str, subcode: str, title: str, category: str, amount: float) -> dict[str, Any]:
        return {
            "id": item_id,
            "subcode": subcode,
            "paid": amount > 0,
            "pricing": {
                "total": {"price": {"amount": float(amount), "currency": currency}},
                "base": {"price": {"amount": float(amount), "currency": currency}},
            },
            # Rich-ish structure (tolerant for various UIs).
            "mealDetails": {
                "category": category,
                "subCategory": "GOURMET" if item_id == "MEAL_GOURMET" else ("DRINKS" if category == "DRINK" else "MEALS"),
                "localizedTitles": {"en_US": title},
                "localizedCategory": {"en_US": "Drinks" if category == "DRINK" else "Meals"},
                "localizedSubCategory": {"en_US": "Gourmet" if item_id == "MEAL_GOURMET" else ("Drinks" if category == "DRINK" else "Meals")},
            },
            # Flat aliases.
            "name": title,
            "category": category,
        }

    return [
        item(item_id="MEAL_GOURMET", subcode="GM", title="gourmet meal", category="MEAL", amount=18.0),
        item(item_id="MEAL_STANDARD", subcode="ST", title="standard meal", category="MEAL", amount=12.0),
        item(item_id="MEAL_VEG", subcode="VG", title="vegetarian meal", category="MEAL", amount=12.0),
        item(item_id="DRINK_WATER", subcode="WA", title="water", category="DRINK", amount=3.0),
        item(item_id="DRINK_SOFT", subcode="SD", title="soft drink", category="DRINK", amount=6.0),
        item(item_id="DRINK_CHAMPAGNE", subcode="CH", title="champagne", category="DRINK", amount=35.0),
    ]


def _catalog_by_id(catalog: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for c in catalog:
        if isinstance(c, dict):
            cid = str(c.get("id") or "").strip()
            if cid:
                out[cid] = c
    return out


def _extract_meal_selections(payload: Any) -> list[dict[str, Any]]:
    """Extract MealSelection-like dicts.

    Supports:
    - MealsSelectionRequest: {"mealSelection": {...}}
    - AncillariesUpdateRequest: {"mealSelections": [{...}, ...]}
    Also tolerates "mealsSelections"/"mealSelections" variations if sent by UI.
    """
    if not isinstance(payload, dict):
        return []

    out: list[dict[str, Any]] = []

    single = payload.get("mealSelection")
    if isinstance(single, dict):
        out.append(_safe_json(single))

    multi = payload.get("mealSelections")
    if multi is None:
        multi = payload.get("mealsSelections")
    if isinstance(multi, dict):
        out.append(_safe_json(multi))
    else:
        for it in _safe_list(multi):
            d = _safe_json(it)
            if d:
                out.append(d)

    normalized: list[dict[str, Any]] = []
    for d in out:
        pid = str(d.get("passengerId") or "").strip()
        sid = str(d.get("segmentId") or d.get("routeId") or "").strip()
        mid = str(d.get("mealId") or d.get("id") or "").strip()
        sub = str(d.get("mealSubcode") or d.get("subcode") or "").strip()
        normalized.append(
            {
                "passengerId": pid,
                "segmentId": sid,
                "mealId": mid,
                "mealSubcode": sub,
                "sameMeal": bool(d.get("sameMeal")) if d.get("sameMeal") is not None else None,
                "redemption": bool(d.get("redemption")) if d.get("redemption") is not None else None,
            }
        )
    return normalized


def _merge_selections(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Replace selection for passenger+segment, keep others."""
    warnings: list[dict[str, Any]] = []
    idx: dict[tuple[str, str], dict[str, Any]] = {}
    for s in existing:
        if not isinstance(s, dict):
            continue
        pid = str(s.get("passengerId") or "").strip()
        sid = str(s.get("segmentId") or "").strip()
        if pid and sid:
            idx[(pid, sid)] = s

    for s in incoming:
        pid = str(s.get("passengerId") or "").strip()
        sid = str(s.get("segmentId") or "").strip()
        mid = str(s.get("mealId") or "").strip()
        if not pid or not sid or not mid:
            warnings.append(
                {
                    "code": "MEAL_SELECTION_INVALID",
                    "message": "Meal selection entry is missing passengerId/segmentId/mealId; ignored.",
                    "details": {"passengerId": pid, "segmentId": sid, "mealId": mid},
                }
            )
            continue
        idx[(pid, sid)] = {"passengerId": pid, "segmentId": sid, **s}

    merged = list(idx.values())
    merged.sort(key=lambda x: (str(x.get("segmentId") or ""), str(x.get("passengerId") or "")))
    return merged, warnings


def _build_meal_items(
    *,
    ctx: RequestContext,
    currency: str,
    catalog: list[dict[str, Any]],
    selections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cat = _catalog_by_id(catalog)
    items: list[dict[str, Any]] = []

    for s in selections:
        pid = str(s.get("passengerId") or "").strip()
        sid = str(s.get("segmentId") or "").strip()
        mid = str(s.get("mealId") or "").strip()
        sub = str(s.get("mealSubcode") or "").strip()

        opt = cat.get(mid)
        if opt is None:
            # Unknown ID; keep it selectable and paid to avoid UI dead-ends.
            category = "DRINK" if "DRINK" in mid.upper() else "MEAL"
            amount = 10.0 if category == "MEAL" else 8.0
            title = mid.replace("_", " ").lower()
        else:
            category = str(opt.get("category") or opt.get("mealDetails", {}).get("category") or "MEAL")
            pricing = _safe_json(_safe_json(opt.get("pricing")).get("total")).get("price")
            amount = float(_safe_json(pricing).get("amount") or 0.0)
            title = str(opt.get("name") or opt.get("mealDetails", {}).get("localizedTitles", {}).get("en_US") or mid)

        item_id = stable_id("meal", f"{ctx.conversation_id}|{pid}|{sid}|{mid}|{sub}", length=14)
        items.append(
            {
                "id": item_id,
                "passengerId": pid,
                "segmentId": sid,
                "mealId": mid,
                "mealSubcode": sub,
                "category": category,
                "name": title,
                "pricing": {"total": {"price": {"amount": float(amount), "currency": currency}}},
            }
        )
    return items


def _attach_existing_ancillaries(shopping_cart: dict[str, Any], air_anc: dict[str, Any]) -> None:
    # Used to keep summaries stable across steps.
    for key in ["seatSelections", "baggageSelections", "baggageItems", "bagItems", "mealSelections", "mealItems"]:
        val = air_anc.get(key)
        if val is not None:
            shopping_cart[key] = val

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
                for key in ["seatSelections", "baggageSelections", "baggageItems", "bagItems", "mealSelections", "mealItems"]:
                    val = air_anc.get(key)
                    if val is not None:
                        anc[key] = val


async def put_select_meals(request: Request) -> JSONResponse:
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
                "message": "State store is not available; meal selections were not persisted.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    store.ensure_from_request(ctx=ctx, path_params=request.path_params)

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    req = _safe_json(body)

    # Currency is determined by existing search (if any) via repricer.
    pricing, currency = _reprice_cart(store, ctx=ctx, order_id=order_id, cart_id=cart_id, air_id=air_id)

    catalog = _meal_catalog(currency)
    incoming = _extract_meal_selections(req)

    air_state, _ = store.ensure_air(order_id, cart_id, air_id)
    existing = air_state.ancillaries.get("mealSelections")
    if not isinstance(existing, list):
        existing = []
    existing_norm = [_safe_json(x) for x in existing]

    merged, warnings = _merge_selections(existing_norm, incoming)
    items = _build_meal_items(ctx=ctx, currency=currency, catalog=catalog, selections=merged)

    air_state.ancillaries["mealOptions"] = catalog
    air_state.ancillaries["mealSelections"] = merged
    air_state.ancillaries["mealItems"] = items
    air_state.updated_at = now_utc_iso()
    air_state.revision = store.touch()

    # Reprice with meals/drinks included (seats._reprice_cart reads mealItems).
    pricing, currency = _reprice_cart(store, ctx=ctx, order_id=order_id, cart_id=cart_id, air_id=air_id)

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = "MEALS"
    shopping_cart["pricing"] = pricing
    shopping_cart["mealOptions"] = catalog
    shopping_cart["mealSelections"] = merged
    shopping_cart["mealItems"] = items
    _attach_existing_ancillaries(shopping_cart, air_state.ancillaries)

    payload.update(
        {
            "retrieve": {"shoppingCart": True, "ancillariesPricing": True},
            "shoppingCart": shopping_cart,
            "mealOptions": catalog,
            "mealSelections": merged,
            "mealItems": items,
        }
    )

    for w in warnings:
        payload["warnings"].append(w)

    mock_meta = {
        "kind": "MealsSelection",
        "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        "count": len(merged),
    }
    if debug_enabled():
        payload["mock"] = mock_meta
    return JSONResponse(payload, status_code=200)


async def put_update_meals(request: Request) -> JSONResponse:
    # AncillariesUpdateRequest path; same logic.
    return await put_select_meals(request)


async def delete_shopping_cart_meals(request: Request) -> JSONResponse:
    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()
    air_id = str(request.path_params.get("airId") or "").strip()

    # API uses segmentId; tolerate routeId too.
    segment_id = str(request.query_params.get("segmentId") or request.query_params.get("routeId") or "").strip()

    payload = ok()
    with_context_warnings(payload, context_warnings=ctx.warnings)

    if store is None:
        payload["warnings"].append(
            {
                "code": "STATE_STORE_MISSING",
                "message": "State store is not available; meal delete was not persisted.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id, "segmentId": segment_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    store.ensure_from_request(ctx=ctx, path_params=request.path_params)
    air_state, _ = store.ensure_air(order_id, cart_id, air_id)

    selections = air_state.ancillaries.get("mealSelections")
    if not isinstance(selections, list):
        selections = []
    selections_norm = [_safe_json(x) for x in selections]

    if segment_id:
        kept = [s for s in selections_norm if str(s.get("segmentId") or "").strip() != segment_id]
    else:
        kept = []

    air_state.ancillaries["mealSelections"] = kept
    air_state.ancillaries["mealItems"] = []
    air_state.updated_at = now_utc_iso()
    air_state.revision = store.touch()

    pricing, currency = _reprice_cart(store, ctx=ctx, order_id=order_id, cart_id=cart_id, air_id=air_id)

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = "MEALS"
    shopping_cart["pricing"] = pricing
    # Keep options available after delete.
    catalog = air_state.ancillaries.get("mealOptions")
    if not isinstance(catalog, list):
        catalog = _meal_catalog(currency)
        air_state.ancillaries["mealOptions"] = catalog
    shopping_cart["mealOptions"] = catalog
    shopping_cart["mealSelections"] = kept
    shopping_cart["mealItems"] = []
    _attach_existing_ancillaries(shopping_cart, air_state.ancillaries)

    payload.update(
        {
            "retrieve": {"shoppingCart": True, "ancillariesPricing": True},
            "shoppingCart": shopping_cart,
            "mealOptions": catalog,
            "mealSelections": kept,
            "mealItems": [],
        }
    )
    payload["warnings"].append(
        {
            "code": "MEAL_SELECTION_CLEARED",
            "message": "Meal selections were cleared in the mock.",
            "details": {"segmentId": segment_id or None},
        }
    )
    if debug_enabled():
        payload["mock"] = {"kind": "MealsDelete", "segmentId": segment_id or None}
    return JSONResponse(payload, status_code=200)
