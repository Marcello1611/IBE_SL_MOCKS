"""Flights search handlers (Step 4).

Implements:
- POST /api/v1/flights/search
- POST /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search

Goal: provide a stable FlightsSearchResponse-shaped payload sufficient for UI flows.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from fastapi import Request
from fastapi.responses import JSONResponse

from ..headers import RequestContext, build_request_context
from ..responses import ok, with_context_warnings
from ..state import MockStateStore
from ..versioning import stable_id
from ..debug import debug_enabled


def _safe_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _iso_local(dt: datetime) -> str:
    # LocalDateTime in API models: no timezone suffix.
    return dt.replace(microsecond=0).isoformat()


def _make_plain_price(amount: float, currency: str) -> dict[str, Any]:
    return {"amount": round(float(amount), 2), "currency": currency}


def _make_price(amount: float, currency: str) -> dict[str, Any]:
    # com.ots.platform_sl.api.v1.model.common.Price
    return {"price": _make_plain_price(amount, currency), "redemption": None}


def _make_pricing(total_amount: float, currency: str) -> dict[str, Any]:
    # com.ots.platform_sl.api.v1.model.common.Pricing
    return {"total": _make_price(total_amount, currency)}


def _airport(code: str, *, terminal: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": code}
    if terminal is not None:
        out["terminal"] = terminal
    return out


def _airline(code: str, *, name: str = "Mock Airlines", flight_number: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": code, "displayCode": code, "name": name}
    if flight_number is not None:
        out["flightNumber"] = flight_number
    return out


def _segment(
    *,
    seg_id: str,
    origin: str,
    destination: str,
    dep: datetime,
    arr: datetime,
    airline_code: str,
    flight_number: str,
) -> dict[str, Any]:
    duration_min = int((arr - dep).total_seconds() // 60)
    return {
        "id": seg_id,
        "departureAirport": _airport(origin, terminal="A"),
        "arrivalAirport": _airport(destination, terminal="B"),
        "departureDate": _iso_local(dep),
        "arrivalDate": _iso_local(arr),
        "departureTimeZone": "UTC",
        "arrivalTimeZone": "UTC",
        "duration": {"amount": duration_min, "unit": "minutes"},
        "marketingAirline": _airline(airline_code, flight_number=flight_number),
        "operatingAirline": _airline(airline_code, flight_number=flight_number),
        "displayAirlineCode": airline_code,
        "statusByCoupons": "OK",
        "actual": False,
    }


def _route(
    *,
    route_id: str,
    origin: str,
    destination: str,
    dep: datetime,
    arr: datetime,
    segments: list[dict[str, Any]],
    fare_family: str,
) -> dict[str, Any]:
    duration_min = int((arr - dep).total_seconds() // 60)
    return {
        "id": route_id,
        "origin": origin,
        "destination": destination,
        "departureDate": _iso_local(dep),
        "arrivalDate": _iso_local(arr),
        "departureTimeZone": "UTC",
        "arrivalTimeZone": "UTC",
        "duration": {"amount": duration_min, "unit": "minutes"},
        "fareFamily": fare_family,
        "segments": segments,
        "stops": [],
        "through": False,
        "transferFare": False,
        "actual": False,
        "statusByCoupons": "OK",
    }


def _solution(
    *,
    sol_id: str,
    fare_family: str,
    cabin: str,
    currency: str,
    amount: float,
    preselected: bool = False,
) -> dict[str, Any]:
    # com.ots.platform_sl.api.v1.model.flights.search.Solution
    return {
        "id": sol_id,
        "code": sol_id,
        "fareFamily": fare_family,
        "alternativeFareFamily": None,
        "cabin": cabin,
        "pricing": _make_pricing(amount, currency),
        "passengerBreakdowns": [],
        "labels": [],
        "preselected": preselected,
        "params": {},
        "availabilityError": None,
        "lowConnectionTime": False,
        "postponedTicketing": False,
        "hideDynamicDiscount": False,
    }


def _build_option(
    *,
    option_id: str,
    order: int,
    origin: str,
    destination: str,
    dep_dt: datetime,
    currency: str,
    base_amount: float,
    direct: bool,
) -> dict[str, Any]:
    # Create 3 fare families per option to support fare-family UI switches.
    fare_families = [
        ("ECONOMYLITE", 0.0),
        ("ECONOMYSTANDARD", 35.0),
        ("ECONOMYFLEX", 85.0),
    ]
    solutions: dict[str, Any] = {}
    cheapest_sol_id: str | None = None

    if direct:
        seg_id = stable_id("seg", f"{option_id}:0")
        dep = dep_dt
        arr = dep + timedelta(hours=2, minutes=15)
        segments = [
            _segment(
                seg_id=seg_id,
                origin=origin,
                destination=destination,
                dep=dep,
                arr=arr,
                airline_code="MO",
                flight_number=str(100 + order),
            )
        ]
        route_id = stable_id("route", f"{option_id}:route")
        route_obj = _route(
            route_id=route_id,
            origin=origin,
            destination=destination,
            dep=dep,
            arr=arr,
            segments=segments,
            fare_family="ECONOMY",
        )
    else:
        # 1 stop via HUB
        hub = "HUB"
        seg1_id = stable_id("seg", f"{option_id}:1")
        seg2_id = stable_id("seg", f"{option_id}:2")
        dep = dep_dt
        arr1 = dep + timedelta(hours=1, minutes=20)
        dep2 = arr1 + timedelta(minutes=55)
        arr2 = dep2 + timedelta(hours=1, minutes=40)
        segments = [
            _segment(
                seg_id=seg1_id,
                origin=origin,
                destination=hub,
                dep=dep,
                arr=arr1,
                airline_code="MO",
                flight_number=str(200 + order),
            ),
            _segment(
                seg_id=seg2_id,
                origin=hub,
                destination=destination,
                dep=dep2,
                arr=arr2,
                airline_code="MO",
                flight_number=str(300 + order),
            ),
        ]
        route_id = stable_id("route", f"{option_id}:route")
        route_obj = _route(
            route_id=route_id,
            origin=origin,
            destination=destination,
            dep=dep,
            arr=arr2,
            segments=segments,
            fare_family="ECONOMY",
        )

    for i, (ff, surcharge) in enumerate(fare_families):
        sol_id = stable_id("sol", f"{option_id}:{ff}")
        amount = base_amount + surcharge
        solutions[sol_id] = _solution(
            sol_id=sol_id,
            fare_family=ff,
            cabin="ECONOMY",
            currency=currency,
            amount=amount,
            preselected=(i == 0),
        )
        if i == 0:
            cheapest_sol_id = sol_id

    return {
        "order": order,
        "id": option_id,
        "routes": [route_obj],
        "solutions": solutions,
        "subsidizedSolutions": [],
        "cheapestSolutionId": cheapest_sol_id,
        "cheapestBusinessSolutionId": None,
        "cheapestSolutionIdWithBaggage": cheapest_sol_id,
        "available": True,
        "insufficientPlaces": False,
        "groupProhibited": False,
        "userSelected": False,
        "soldOut": False,
        "availablePets": [],
        "unchanged": False,
        "labels": [],
    }


def _build_option_set(
    *,
    index: int,
    origin: str,
    destination: str,
    departure_date: str,
    currency: str,
    seed: str,
) -> dict[str, Any]:
    # departure_date in YYYY-MM-DD
    dep_dt = datetime.fromisoformat(departure_date + "T08:00:00")
    set_id = stable_id("optset", f"{seed}:{index}")
    opt1_id = stable_id("opt", f"{set_id}:cheap")
    opt2_id = stable_id("opt", f"{set_id}:fast")
    opt3_id = stable_id("opt", f"{set_id}:conv")

    options = [
        _build_option(
            option_id=opt1_id,
            order=1,
            origin=origin,
            destination=destination,
            dep_dt=dep_dt,
            currency=currency,
            base_amount=119.0 + index * 15,
            direct=False,
        ),
        _build_option(
            option_id=opt2_id,
            order=2,
            origin=origin,
            destination=destination,
            dep_dt=dep_dt + timedelta(hours=2),
            currency=currency,
            base_amount=149.0 + index * 15,
            direct=True,
        ),
        _build_option(
            option_id=opt3_id,
            order=3,
            origin=origin,
            destination=destination,
            dep_dt=dep_dt + timedelta(hours=4),
            currency=currency,
            base_amount=179.0 + index * 15,
            direct=True,
        ),
    ]

    # default selection: cheapest option + its cheapest solution
    cheapest_option = options[0]
    cheapest_option_id = cheapest_option["id"]
    cheapest_solution_id = cheapest_option.get("cheapestSolutionId")

    return {
        "id": set_id,
        "index": index,
        "options": options,
        "selection": {"optionId": cheapest_option_id, "solutionId": cheapest_solution_id},
        "optionId": cheapest_option_id,
        "solutionId": cheapest_solution_id,
        "sort": "CHEAPEST",
        "histogram": None,
        "flightCalendar": None,
        "flightFilter": None,
        "advertisingCampaign": None,
        "cheapestOptionId": cheapest_option_id,
        "fastestOptionId": options[1]["id"],
        "mostConvenientOptionId": options[2]["id"],
    }


def _extract_routes(search_params: dict[str, Any]) -> list[dict[str, str]]:
    routes = _safe_list(search_params.get("routes"))
    out: list[dict[str, str]] = []
    for r in routes:
        rr = _safe_json(r)
        origin = str(rr.get("origin") or "").strip() or "AAA"
        destination = str(rr.get("destination") or "").strip() or "BBB"
        dep_date = str(rr.get("departureDate") or "").strip() or "2026-02-01"
        out.append({"origin": origin, "destination": destination, "departureDate": dep_date})
    if not out:
        out.append({"origin": "AAA", "destination": "BBB", "departureDate": "2026-02-01"})
    return out


def _search_key(ctx: RequestContext, search_params: dict[str, Any]) -> str:
    routes = _extract_routes(search_params)
    trip_type = str(search_params.get("tripType") or "ONE_WAY")
    parts = [ctx.conversation_id, ctx.flow, trip_type]
    for r in routes:
        parts.extend([r["origin"], r["destination"], r["departureDate"]])
    return "|".join(parts)


def _ensure_bundle(store: MockStateStore, ctx: RequestContext, search_key: str) -> tuple[str, str, str]:
    existing = store.get_search_bundle(ctx=ctx, search_key=search_key)
    if existing:
        return existing

    # Deterministic IDs per (conversation, search_key)
    order_id = stable_id("order", search_key, length=16)
    cart_id = stable_id("cart", search_key, length=16)
    air_id = stable_id("air", search_key, length=16)

    store.ensure_search_bundle(ctx=ctx, search_key=search_key, order_id=order_id, cart_id=cart_id, air_id=air_id)
    store.ensure_order(order_id, ctx)
    store.ensure_shopping_cart(order_id, cart_id)
    store.ensure_air(order_id, cart_id, air_id)

    # Link air to cart & order for downstream calls.
    order, _ = store.ensure_order(order_id, ctx)
    order.added_air_id = air_id
    cart, _ = store.ensure_shopping_cart(order_id, cart_id)
    if air_id not in cart.selected_airs:
        cart.selected_airs.append(air_id)

    return order_id, cart_id, air_id


def _build_shopping_cart_payload(*, order_id: str, cart_id: str, air_id: str, currency: str) -> dict[str, Any]:
    return {
        "id": cart_id,
        "status": "OPEN",
        "step": "FLIGHTS_SEARCH",
        "currentCurrency": currency,
        "currencies": [currency],
        "tripType": None,
        "products": [],
        "pricing": _make_pricing(0.0, currency),
        "order": {
            "id": order_id,
            "number": order_id,
            "status": "DRAFT",
            "addedAirId": air_id,
            "airs": [{"id": air_id}],
            "passengers": [],
            "payments": [],
            "transfers": [],
            "offline": False,
            "snapshot": False,
        },
        "customer": {},
        "searchLink": None,
    }


async def post_flights_search(request: Request) -> JSONResponse:
    """POST /api/v1/flights/search"""
    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    req = _safe_json(body)
    search_params = _safe_json(req.get("searchParams"))
    currency = str(search_params.get("currency") or "USD")

    key = _search_key(ctx, search_params)
    if store is None:
        order_id = stable_id("order", key, length=16)
        cart_id = stable_id("cart", key, length=16)
        air_id = stable_id("air", key, length=16)
    else:
        order_id, cart_id, air_id = _ensure_bundle(store, ctx, key)

    routes = _extract_routes(search_params)
    option_sets = []
    for idx, r in enumerate(routes):
        option_sets.append(
            _build_option_set(
                index=idx,
                origin=r["origin"],
                destination=r["destination"],
                departure_date=r["departureDate"],
                currency=currency,
                seed=key,
            )
        )

    search_obj = {
        "searchParams": search_params,
        "optionSets": option_sets,
        "advertisingCampaign": None,
        "flightAlternatives": [],
        "radiusFlight": None,
        "withPersonalPromoCode": False,
        "penalty": None,
    }

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)

    if store is not None:
        # Persist the search object for later steps.
        cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)
        cart_state.flights_search = search_obj

        air_state, _ = store.ensure_air(order_id, cart_id, air_id)
        # Keep a lightweight segments list for follow-up endpoints.
        segs: list[dict[str, Any]] = []
        for os_ in option_sets:
            for opt in os_.get("options", []):
                for rt in opt.get("routes", []):
                    for seg in rt.get("segments", []):
                        segs.append({"id": seg.get("id"), "from": rt.get("origin"), "to": rt.get("destination")})
        air_state.segments = segs

    payload = ok(
        {
            "retrieve": {"shoppingCart": True, "ancillariesPricing": False},
            "shoppingCart": shopping_cart,
            "search": search_obj,
            "forwardingParams": {},
            "deeplinkStep": None,
            "redirectUrl": None,
        }
    )
    with_context_warnings(payload, context_warnings=ctx.warnings)
    if debug_enabled():
        payload["mock"] = {
            "kind": "FlightsSearchResponse",
            "searchKey": key,
            "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        }
    return JSONResponse(payload, status_code=200)


async def post_flights_search_with_cart(request: Request) -> JSONResponse:
    """POST /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search"""
    ctx: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))
    store: MockStateStore | None = getattr(request.state, "store", None)
    if store is None:
        store = getattr(request.app.state, "store", None)  # type: ignore[attr-defined]

    order_id = str(request.path_params.get("orderId") or "").strip()
    cart_id = str(request.path_params.get("shoppingCartId") or "").strip()

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    req = _safe_json(body)
    search_params = _safe_json(req.get("searchParams"))
    currency = str(search_params.get("currency") or "USD")

    # If we have a store, keep the cart stable and create a deterministic airId for this search.
    key = _search_key(ctx, search_params)
    air_id = stable_id("air", key, length=16)

    if store is not None:
        store.ensure_order(order_id, ctx)
        store.ensure_shopping_cart(order_id, cart_id)
        store.ensure_air(order_id, cart_id, air_id)
        order_state, _ = store.ensure_order(order_id, ctx)
        order_state.added_air_id = air_id

    routes = _extract_routes(search_params)
    option_sets = []
    for idx, r in enumerate(routes):
        option_sets.append(
            _build_option_set(
                index=idx,
                origin=r["origin"],
                destination=r["destination"],
                departure_date=r["departureDate"],
                currency=currency,
                seed=key,
            )
        )

    search_obj = {
        "searchParams": search_params,
        "optionSets": option_sets,
        "advertisingCampaign": None,
        "flightAlternatives": [],
        "radiusFlight": None,
        "withPersonalPromoCode": False,
        "penalty": None,
    }

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)

    if store is not None:
        cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)
        cart_state.flights_search = search_obj
        air_state, _ = store.ensure_air(order_id, cart_id, air_id)
        segs: list[dict[str, Any]] = []
        for os_ in option_sets:
            for opt in os_.get("options", []):
                for rt in opt.get("routes", []):
                    for seg in rt.get("segments", []):
                        segs.append({"id": seg.get("id"), "from": rt.get("origin"), "to": rt.get("destination")})
        air_state.segments = segs

    payload = ok(
        {
            "retrieve": {"shoppingCart": True, "ancillariesPricing": False},
            "shoppingCart": shopping_cart,
            "search": search_obj,
            "forwardingParams": {},
            "deeplinkStep": None,
            "redirectUrl": None,
        }
    )
    with_context_warnings(payload, context_warnings=ctx.warnings)
    if debug_enabled():
        payload["mock"] = {
            "kind": "FlightsSearchResponse",
            "searchKey": key,
            "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
        }
    return JSONResponse(payload, status_code=200)


def _resolve_air_id_for_cart(store: MockStateStore, ctx: RequestContext, order_id: str, cart_id: str) -> str:
    """Resolve current airId for an (order, cart) pair."""

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


async def get_flights_search_with_cart(request: Request) -> JSONResponse:
    """GET /api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search

    Returns the last stored search context for the cart (if any).
    """

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
                "message": "State store is not available; search context cannot be retrieved.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id},
            }
        )
        return JSONResponse(payload, status_code=200)

    store.ensure_order(order_id, ctx)
    cart_state, _ = store.ensure_shopping_cart(order_id, cart_id)

    search_obj = _safe_json(cart_state.flights_search)
    search_params = _safe_json(search_obj.get("searchParams")) if search_obj else {}
    currency = str(search_params.get("currency") or "USD")

    air_id = _resolve_air_id_for_cart(store, ctx, order_id, cart_id)

    shopping_cart = _build_shopping_cart_payload(order_id=order_id, cart_id=cart_id, air_id=air_id, currency=currency)
    # Preserve last computed pricing if available.
    if isinstance(cart_state.pricing, dict) and cart_state.pricing:
        shopping_cart["pricing"] = cart_state.pricing
    else:
        shopping_cart["pricing"] = _make_pricing(0.0, currency)

    payload.update(
        {
            "retrieve": {"shoppingCart": True, "ancillariesPricing": False},
            "shoppingCart": shopping_cart,
            "search": search_obj if search_obj else None,
            "forwardingParams": {},
            "deeplinkStep": None,
            "redirectUrl": None,
        }
    )

    if not search_obj:
        payload["warnings"].append(
            {
                "code": "NO_SEARCH_CONTEXT",
                "message": "No flights search context found in the cart.",
                "details": {"orderId": order_id, "shoppingCartId": cart_id},
            }
        )

    if debug_enabled():
        payload["mock"] = {
            "kind": "FlightsSearchGet",
            "ids": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
            "hasSearch": bool(search_obj),
        }

    return JSONResponse(payload, status_code=200)
