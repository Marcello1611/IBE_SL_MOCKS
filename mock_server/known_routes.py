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
    - Auto-create referenced entities (order/cart/air) to keep stateful flows stable.
    """

    try:
        # Ensure body bytes are cached for later steps (and to keep behavior stable).
        body_bytes = await request.body()
        request.scope["_body"] = body_bytes
    except Exception:  # noqa: BLE001
        request.scope["_body"] = b""  # best-effort

    context: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))

    payload = ok()
    with_context_warnings(payload, context_warnings=context.warnings)
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


def register_known_routes(app: FastAPI) -> None:
    """Register all known routes (Step 2)."""

    # Group by (path) and register methods together.
    for item in KNOWN_ROUTES:
        path = item["path"]
        methods = item["methods"]
        # FastAPI/Starlette will match these before the catch-all route
        # if they are added earlier.
        app.add_route(path, _known_stub, methods=methods)
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


