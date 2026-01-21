"""Registry of known endpoints for the IBE mock.

Step 2 objective:
- Ensure all endpoints from FlightsRest, BookingsRest, InsuranceRest, ProfileRest
  are explicitly matched before the /api/v1/* catch-all.
- Each endpoint currently returns a stable BaseResponse-shaped JSON with a
  NOT_IMPLEMENTED warning (not an error), so UI flows do not crash.

Later steps replace stubs with stateful behavior.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .headers import RequestContext, build_request_context
from .responses import ok, with_context_warnings
from .state import MockStateStore
from .handlers.cabins import get_cabins_cart, get_cabins_cart_short, get_cabins_postsell, get_cabins_v2
from .handlers.flights_search import post_flights_search, post_flights_search_with_cart
from .handlers.flights_selection import (
    put_deselect_options,
    put_select_option_solution,
    selection_confirmation,
)
from .handlers.seats import post_seats_preselect, post_special_assistance_seats_update, put_ancillaries_seats, put_or_delete_seats


log = logging.getLogger("mock_server.known_routes")

# Each item: {'path': str, 'methods': [str], 'resources': [str]}
KNOWN_ROUTES: list[dict[str, Any]] = [
  {
    'path': '/api/v1/flights/calendar/search',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/flights/search',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/flights/search/airlines',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/flights/search/deeplink',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/flights/search/passengers',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/flights/servicePassengersData',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/flights/subscribe',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/flights/upgrade/aircrafts',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/flights/upgrade/airlines',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/miles/calculator',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/minPrice/city',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/airs/{airId}/cabins',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/airs/{airId}/flight-change-proposals/search',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/airs/{airId}/passengers/{passengerId}/pet',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/airs/{airId}/segments/{segmentId}/passengers/{passengerId}/cabins',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/flights/fare-rules',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/ancillaries',
    'methods': [
      'DELETE',
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/ancillaries/bags',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/ancillaries/confirmation',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/ancillaries/meals',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/ancillaries/seats',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/auto-checkins',
    'methods': [
      'DELETE'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/autoCheckins',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/baggage',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/bags',
    'methods': [
      'DELETE'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/cabins',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/carbon-offsets',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/check/visa/required',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/dafars',
    'methods': [
      'DELETE',
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/esims',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/fast-tracks',
    'methods': [
      'DELETE',
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/flightChanges',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/flights-ancillaries',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/free-refunds',
    'methods': [
      'DELETE',
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/lounges',
    'methods': [
      'DELETE',
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/marketplace-products',
    'methods': [
      'DELETE'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/meals',
    'methods': [
      'DELETE',
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/miles',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/pets',
    'methods': [
      'DELETE',
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/pets/availability',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/pets/confirm',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/prepays',
    'methods': [
      'DELETE',
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/preseat/suggestion',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/restrict/residences',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/seats',
    'methods': [
      'DELETE',
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/seats/preselect',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/special-assistance-seats/update',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/special-assistance/update',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/tariff/{tariffId}',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/upgrades',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/ancillaries/special-assistance/confirmation',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/bookings',
    'methods': [
      'POST'
    ],
    'resources': [
      'BookingsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/deposit',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/documents/options',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/extraseat/seats/preselect',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/fare-rules',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search',
    'methods': [
      'GET',
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/check/campaign',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/deeplink',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/deselect/options',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/histogram',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/optionSets/{optionSetId}/histogram/{shiftDays}',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/optionSets/{optionSetId}/option/{optionId}/solution/{solutionId}',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/restore',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/selection/confirmation',
    'methods': [
      'DELETE',
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/insurances',
    'methods': [
      'DELETE',
      'GET',
      'PUT'
    ],
    'resources': [
      'InsuranceRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/products/cashless_unsupported',
    'methods': [
      'DELETE'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/sms',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/taxes',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/orders/{orderId}/special-assistance/confirmation',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/profile',
    'methods': [
      'POST',
      'PUT'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/availability',
    'methods': [
      'GET'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/ffpSuggest',
    'methods': [
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/loyalty-program/search',
    'methods': [
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/orders/{orderId}/create-miles-surcharge',
    'methods': [
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/orders/{orderId}/shoppingCarts/{shoppingCartId}/customer',
    'methods': [
      'PUT'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/orders/{orderId}/shoppingCarts/{shoppingCartId}/miles/transaction',
    'methods': [
      'DELETE',
      'GET',
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/orders/{orderId}/shoppingCarts/{shoppingCartId}/miles/transaction/resending',
    'methods': [
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/password-policies',
    'methods': [
      'GET'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/phone/confirmation',
    'methods': [
      'PUT'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/phone/confirmation/code',
    'methods': [
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/profile',
    'methods': [
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/profiles',
    'methods': [
      'GET'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/resend-profile-confirmation',
    'methods': [
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/session',
    'methods': [
      'DELETE',
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/session/operator',
    'methods': [
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/subscriptions',
    'methods': [
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/synchronization',
    'methods': [
      'PUT'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/traveller',
    'methods': [
      'PUT'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/travellers',
    'methods': [
      'GET',
      'POST'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/profile/{deviceId}',
    'methods': [
      'GET'
    ],
    'resources': [
      'ProfileRest'
    ]
  },
  {
    'path': '/api/v1/reissue/orders/{orderId}/airs/{airId}/calendar/search',
    'methods': [
      'POST'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/shoppingCarts/{shoppingCartId}/airs/{airId}/cabins',
    'methods': [
      'GET'
    ],
    'resources': [
      'FlightsRest'
    ]
  },
  {
    'path': '/api/v1/upsell/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/optionSets/{optionSetId}/option/{optionId}/solution/{solutionId}',
    'methods': [
      'PUT'
    ],
    'resources': [
      'FlightsRest'
    ]
  }
]



async def _known_stub(request: Request) -> JSONResponse:
    """Default stub handler for known endpoints.

    Policy:
    - Always return HTTP 200 with BaseResponse-shaped JSON.
    - Never raise.
    - Add context warnings (missing headers).
    - Auto-create referenced entities (order/cart/air/profile) to keep stateful flows stable.
    """

    try:
        # Ensure body bytes are cached for later steps (and to keep behavior stable).
        body_bytes = await request.body()
        request.scope["_body"] = body_bytes
    except Exception:  # noqa: BLE001
        request.scope["_body"] = b""  # best-effort

    context: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))

    # Ensure referenced entities exist (best-effort, never raising).
    store = MockStateStore.get()
    auto_created = store.ensure_from_request(ctx=context, path_params=request.path_params)

    payload = ok(
        {
            "_mock": {
                "revision": store.global_revision,
            }
        }
    )
    with_context_warnings(payload, context_warnings=context.warnings)
    for w in auto_created:
        payload["warnings"].append(w)

    payload["warnings"].append(
        {
            "code": "NOT_IMPLEMENTED",
            "message": "Known endpoint stubbed by mock (implementation pending).",
            "details": {
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.query_params),
            },
        }
    )
    return JSONResponse(payload, status_code=200)


def _override_handler(path: str, methods: list[str]):
    """Return a stateful handler for a known route, or None.

    Keeping matching explicit here prevents accidental shadowing by the /api/v1/* catch-all.
    """

    # Step 4: flights search (initial + cart-bound).
    if path == "/api/v1/flights/search" and "POST" in methods:
        return post_flights_search
    if path == "/api/v1/flights/search/deeplink" and "POST" in methods:
        return post_flights_search
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search" and "POST" in methods:
        return post_flights_search_with_cart

    # Step 5: choose option/solution inside flights search.
    if (
        path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/optionSets/{optionSetId}/option/{optionId}/solution/{solutionId}"
        and "PUT" in methods
    ):
        return put_select_option_solution
    if (
        path == "/api/v1/upsell/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/optionSets/{optionSetId}/option/{optionId}/solution/{solutionId}"
        and "PUT" in methods
    ):
        return put_select_option_solution
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/deselect/options" and "PUT" in methods:
        return put_deselect_options
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/flights/search/selection/confirmation" and (
        "POST" in methods or "DELETE" in methods
    ):
        return selection_confirmation

    # Step 6: full seat map (cabins).
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/cabins" and "GET" in methods:
        return get_cabins_cart
    if path == "/api/v1/shoppingCarts/{shoppingCartId}/airs/{airId}/cabins" and "GET" in methods:
        return get_cabins_cart_short
    if path == "/api/v1/orders/{orderId}/airs/{airId}/cabins" and "GET" in methods:
        return get_cabins_postsell
    if path == "/api/v1/orders/{orderId}/airs/{airId}/segments/{segmentId}/passengers/{passengerId}/cabins" and "GET" in methods:
        return get_cabins_v2

    # Step 7: seat selection (stateful).
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/seats" and ("PUT" in methods or "DELETE" in methods):
        return put_or_delete_seats
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/ancillaries/seats" and "PUT" in methods:
        return put_ancillaries_seats
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/seats/preselect" and ("POST" in methods or "PUT" in methods):
        return post_seats_preselect
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/preseat/suggestion" and "POST" in methods:
        return post_seats_preselect
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/extraseat/seats/preselect" and "POST" in methods:
        return post_seats_preselect
    if path == "/api/v1/orders/{orderId}/shoppingCarts/{shoppingCartId}/airs/{airId}/special-assistance-seats/update" and "POST" in methods:
        return post_special_assistance_seats_update

    return None


def register_known_routes(app: FastAPI) -> None:
    """Register all known routes (Step 2+)."""

    for item in KNOWN_ROUTES:
        path = item["path"]
        methods = item["methods"]

        handler = _override_handler(path, methods) or _known_stub
        app.add_route(path, handler, methods=methods)
