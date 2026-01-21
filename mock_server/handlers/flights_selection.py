"""Flights selection handlers (Step 5).

Implements minimal stateful selection/confirmation logic for flights search.

Covered endpoints:
- PUT /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/optionSets/{optionSetId}/option/{optionId}/solution/{solutionId}
- PUT /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/deselect/options
- POST/DELETE /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/selection/confirmation

The real backend returns richer DTOs; the mock focuses on:
- stable response envelope
- consistent shoppingCart payload
- preserved selection in state store
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ..headers import RequestContext, build_request_context
from ..responses import ok, with_context_warnings
from ..state import MockStateStore
from ..versioning import now_utc_iso

# Reuse helpers to keep shapes aligned with search payloads.
from .flights_search import _build_shopping_cart_payload, _make_pricing, _safe_json


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _resolve_air_id(store: MockStateStore, ctx: RequestContext, order_id: str, cart_id: str) -> str:
    """Resolve current airId for the (order, cart) context."""

    order_state, _ = store.ensure_order(order_id, ctx)
    if order_state.added_air_id:
        return order_state.added_air_id

    cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)
    if cart_state.selected_airs:
        return cart_state.selected_airs[0]

    air_id = f"air-{order_id}"
    store.ensure_air(order_id, cart_id, air_id)
    cart_state.selected_airs.append(air_id)
    order_state.added_air_id = air_id
    store.touch()
    return air_id


def _find_option_set(search_obj: dict[str, Any], option_set_id: str) -> dict[str, Any] | None:
    for os_ in _safe_list(search_obj.get("optionSets")):
        d = _safe_json(os_)
        if str(d.get("id")) == option_set_id:
            return d
    return None


def _find_option(option_set: dict[str, Any], option_id: str) -> dict[str, Any] | None:
    for opt in _safe_list(option_set.get("options")):
        d = _safe_json(opt)
        if str(d.get("id")) == option_id:
            return d
    return None


def _extract_solution_price(option: dict[str, Any], solution_id: str) -> tuple[float, str] | None:
    solutions = option.get("solutions")
    if not isinstance(solutions, dict):
        return None
    sol = solutions.get(solution_id)
    if not isinstance(sol, dict):
        return None
    pricing = sol.get("pricing")
    if not isinstance(pricing, dict):
        return None
    total = pricing.get("total")
    if not isinstance(total, dict):
        return None
    price = total.get("price")
    if not isinstance(price, dict):
        return None
    try:
        amount = float(price.get("amount"))
    except Exception:  # noqa: BLE001
        return None
    currency = str(price.get("currency") or "USD")
    return amount, currency


def _compute_total(search_obj: dict[str, Any]) -> tuple[float, str]:
    total_amount = 0.0
    currency = "USD"
    for os_ in _safe_list(search_obj.get("optionSets")):
        option_set = _safe_json(os_)
        sel = _safe_json(option_set.get("selection"))
        option_id = str(sel.get("optionId") or option_set.get("optionId") or "")
        solution_id = str(sel.get("solutionId") or option_set.get("solutionId") or "")
        if not option_id:
            continue
        opt = _find_option(option_set, option_id)
        if not opt:
            continue
        if not solution_id:
            solution_id = str(opt.get("cheapestSolutionId") or "")
        if not solution_id:
            continue
        res = _extract_solution_price(opt, solution_id)
        if not res:
            continue
        amount, cur = res
        currency = cur or currency
        total_amount += amount
    return total_amount, currency


def _mark_selected(option_set: dict[str, Any], option_id: str, solution_id: str) -> None:
    # Mark option selection
    for opt in _safe_list(option_set.get("options")):
        od = _safe_json(opt)
        od["userSelected"] = str(od.get("id")) == option_id
        # Mark solution selection within option
        solutions = od.get("solutions")
        if isinstance(solutions, dict):
            for sid, sol in solutions.items():
                if isinstance(sol, dict):
                    sol["preselected"] = str(sid) == solution_id


def _selected_routes(search_obj: dict[str, Any]) -> list[dict[str, Any]]:
    routes_out: list[dict[str, Any]] = []
    for os_ in _safe_list(search_obj.get("optionSets")):
        option_set = _safe_json(os_)
        sel = _safe_json(option_set.get("selection"))
        option_id = str(sel.get("optionId") or option_set.get("optionId") or "")
        if not option_id:
            continue
        opt = _find_option(option_set, option_id)
        if not opt:
            continue
        for rt in _safe_list(opt.get("routes")):
            rd = _safe_json(rt)
            routes_out.append(rd)
    return routes_out


async def put_select_option_solution(request: Request) -> JSONResponse:
    """Select a (optionId, solutionId) inside an option set."""

    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()
    option_set_id = str(request.path_params.get("optionSetId") or "").strip()
    option_id = str(request.path_params.get("optionId") or "").strip()
    solution_id = str(request.path_params.get("solutionId") or "").strip()

    payload = ok()
    with_context_warnings(payload, context_warnings=ctx.warnings)

    if store is None:
        payload["warnings"].append(
            {
                "code": "STATE_STORE_MISSING",
                "message": "State store is not available; selection was not persisted.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    store.ensure_order(order_id, ctx)
    cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)

    search_obj = _safe_json(cart_state.flights_search)
    if not search_obj:
        payload["warnings"].append(
            {
                "code": "NO_SEARCH_CONTEXT",
                "message": "No flights search context found in the cart; selection ignored.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    option_set = _find_option_set(search_obj, option_set_id)
    if not option_set:
        payload["warnings"].append(
            {
                "code": "OPTION_SET_NOT_FOUND",
                "message": "Option set not found in the current search; selection ignored.",
                "details": {"optionSetId": option_set_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    option = _find_option(option_set, option_id)
    if not option:
        payload["warnings"].append(
            {
                "code": "OPTION_NOT_FOUND",
                "message": "Option not found in the option set; selection ignored.",
                "details": {"optionId": option_id, "optionSetId": option_set_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    # Persist selection in the stored search object.
    option_set["selection"] = {"optionId": option_id, "solutionId": solution_id}
    option_set["optionId"] = option_id
    option_set["solutionId"] = solution_id
    _mark_selected(option_set, option_id, solution_id)

    total_amount, currency = _compute_total(search_obj)
    cart_state.pricing = _make_pricing(total_amount, currency)
    cart_state.updated_at = now_utc_iso()
    cart_state.revision = store.touch()

    air_id = _resolve_air_id(store, ctx, order_id, cart_id)
    air_state, _ = store.ensure_air(order_id, cart_id, air_id)
    air_state.updated_at = now_utc_iso()
    air_state.revision = store.touch()
    air_state.ancillaries.setdefault("flightsSelection", {})
    air_state.ancillaries["flightsSelection"] = {
        "confirmed": False,
        "optionSetId": option_set_id,
        "optionId": option_id,
        "solutionId": solution_id,
    }

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = "FLIGHTS_SELECTION"
    shopping_cart["pricing"] = _make_pricing(total_amount, currency)

    # Enrich the air in the order with selected routes for UI summaries.
    routes = _selected_routes(search_obj)
    if shopping_cart.get("order", {}).get("airs") and routes:
        shopping_cart["order"]["airs"][0]["routes"] = routes

    payload.update(
        {
            "retrieve": {"shoppingCart": True, "ancillariesPricing": False},
            "shoppingCart": shopping_cart,
            "search": search_obj,
            "forwardingParams": {},
            "deeplinkStep": None,
            "redirectUrl": None,
        }
    )
    payload["mock"] = {
        "kind": "FlightsSelection",
        "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        "selection": {"optionSetId": option_set_id, "optionId": option_id, "solutionId": solution_id},
        "total": {"amount": round(total_amount, 2), "currency": currency},
    }
    return JSONResponse(payload, status_code=200)


async def put_deselect_options(request: Request) -> JSONResponse:
    """Reset selection to default (cheapest) for all option sets."""

    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()

    payload = ok()
    with_context_warnings(payload, context_warnings=ctx.warnings)

    if store is None:
        payload["warnings"].append({"code": "STATE_STORE_MISSING", "message": "State store is not available."})
        return JSONResponse(payload, status_code=200)

    cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)
    search_obj = _safe_json(cart_state.flights_search)
    if not search_obj:
        payload["warnings"].append({"code": "NO_SEARCH_CONTEXT", "message": "No search context to reset."})
        return JSONResponse(payload, status_code=200)

    for os_ in _safe_list(search_obj.get("optionSets")):
        option_set = _safe_json(os_)
        cheapest_option_id = str(option_set.get("cheapestOptionId") or "")
        if not cheapest_option_id:
            opts = _safe_list(option_set.get("options"))
            if opts:
                cheapest_option_id = str(_safe_json(opts[0]).get("id") or "")
        opt = _find_option(option_set, cheapest_option_id) if cheapest_option_id else None
        if not opt:
            continue
        cheapest_solution_id = str(opt.get("cheapestSolutionId") or option_set.get("solutionId") or "")
        option_set["selection"] = {"optionId": cheapest_option_id, "solutionId": cheapest_solution_id}
        option_set["optionId"] = cheapest_option_id
        option_set["solutionId"] = cheapest_solution_id
        _mark_selected(option_set, cheapest_option_id, cheapest_solution_id)

    total_amount, currency = _compute_total(search_obj)
    cart_state.pricing = _make_pricing(total_amount, currency)
    cart_state.selection_confirmed = False
    cart_state.updated_at = now_utc_iso()
    cart_state.revision = store.touch()

    air_id = _resolve_air_id(store, ctx, order_id, cart_id)
    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = "FLIGHTS_SEARCH"
    shopping_cart["pricing"] = _make_pricing(total_amount, currency)

    payload.update({"shoppingCart": shopping_cart, "search": search_obj})
    payload["mock"] = {"kind": "FlightsDeselect", "ids": {"orderId": order_id, "shoppingCartId": cart_id}}
    return JSONResponse(payload, status_code=200)


async def selection_confirmation(request: Request) -> JSONResponse:
    """POST/DELETE confirmation for current flight selection."""

    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()

    payload = ok()
    with_context_warnings(payload, context_warnings=ctx.warnings)

    if store is None:
        payload["warnings"].append({"code": "STATE_STORE_MISSING", "message": "State store is not available."})
        return JSONResponse(payload, status_code=200)

    cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)
    search_obj = _safe_json(cart_state.flights_search)
    total_amount, currency = _compute_total(search_obj) if search_obj else (0.0, "USD")

    if request.method.upper() == "POST":
        cart_state.selection_confirmed = True
        step = "ANCILLARIES"
        confirmed = True
    else:
        cart_state.selection_confirmed = False
        step = "FLIGHTS_SELECTION"
        confirmed = False

    cart_state.pricing = _make_pricing(total_amount, currency)
    cart_state.updated_at = now_utc_iso()
    cart_state.revision = store.touch()

    air_id = _resolve_air_id(store, ctx, order_id, cart_id)
    air_state, _ = store.ensure_air(order_id, cart_id, air_id)
    air_state.updated_at = now_utc_iso()
    air_state.revision = store.touch()
    air_state.ancillaries.setdefault("flightsSelection", {})
    air_state.ancillaries["flightsSelection"]["confirmed"] = confirmed

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    shopping_cart["step"] = step
    shopping_cart["pricing"] = _make_pricing(total_amount, currency)
    routes = _selected_routes(search_obj) if search_obj else []
    if shopping_cart.get("order", {}).get("airs") and routes:
        shopping_cart["order"]["airs"][0]["routes"] = routes

    payload.update({"shoppingCart": shopping_cart})
    payload["mock"] = {
        "kind": "FlightsSelectionConfirmation",
        "confirmed": confirmed,
        "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        "total": {"amount": round(total_amount, 2), "currency": currency},
    }
    return JSONResponse(payload, status_code=200)
