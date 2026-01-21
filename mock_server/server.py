"""HTTP server and catch-all routing for the mock.

Step 1 objective:
  - Provide a working HTTP service.
  - Ensure no request results in an unhandled exception (no 500 propagation).
  - Provide a catch-all handler for /api/v1/* for all common methods.

Step 2 objective:
  - Explicitly match endpoints from FlightsRest/BookingsRest/InsuranceRest/ProfileRest
    before the catch-all, returning stable stub responses.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from .errors import error_from_exception
from .headers import RequestContext, build_request_context
from .responses import fail, ok, with_context_warnings
from .known_routes import register_known_routes
from .state import MockStateStore


def _safe_json_body(request: Request) -> Any | None:
    """Parse JSON request body safely.

    Policy: never raise; return None on any parse/IO error.
    """

    try:
        content_type = (request.headers.get("content-type") or "").lower()
        if "application/json" not in content_type:
            return None
    except Exception:
        return None

    # starlette provides request.json(), but we prefer reading bytes once to keep
    # behavior predictable under middleware/exception handling.
    try:
        body = request.scope.get("_body")  # type: ignore[attr-defined]
        if body is None:
            # We cannot await here; this helper is used only in async handlers.
            return None
        if not body:
            return None
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def create_app() -> FastAPI:
    app = FastAPI(
        title="IBE Mock Server",
        version="0.0.1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Global in-memory state store (handlers rely on it).
    app.state.store = MockStateStore()  # type: ignore[attr-defined]

    # Browser UIs and tunneled setups frequently require permissive CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    @app.middleware("http")
    async def _exception_guard(request: Request, call_next):
        """Ensure unexpected exceptions never escape as framework 500s."""

        context = build_request_context(request.headers)
        request.state.ctx = context
        request.state.store = app.state.store  # type: ignore[attr-defined]
        # Cache request body bytes once for consistency across handlers.
        # Starlette caches request.body() internally as well, but we keep a copy
        # in scope to support lightweight parsers without extra awaits.
        try:
            body_bytes = await request.body()
            request.scope["_body"] = body_bytes
        except Exception:  # noqa: BLE001
            request.scope["_body"] = b""
        try:
            response: Response = await call_next(request)
            return response
        except Exception as exc:  # noqa: BLE001
            # Stable error envelope; by default we return HTTP 200 to prevent UI
            # codepaths that treat non-2xx as fatal.
            payload = fail(error_from_exception(exc))
            with_context_warnings(payload, context_warnings=context.warnings)
            return JSONResponse(payload, status_code=200)

    @app.get("/")
    async def root():
        return ok({"status": "ok"})

    @app.get("/healthz")
    async def healthz():
        return ok({"status": "ok"})

    # Step 2: register known API routes before catch-all.
    # These are currently stubbed (BaseResponse + NOT_IMPLEMENTED warning).
    register_known_routes(app)

    @app.api_route(
        "/api/v1/{full_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )
    async def api_v1_catch_all(full_path: str, request: Request):
        """Catch-all for any /api/v1/* request.

        Step 1 behavior:
        - Always returns JSON in the BaseResponse shape.
        - Does not attempt to enforce schema/validation.
        - Adds warnings for missing standard headers.
        - Adds a warning indicating this endpoint is currently unimplemented.
        """

        context: RequestContext = getattr(request.state, "ctx", build_request_context(request.headers))

        _ = _safe_json_body(request)  # parsed body is currently unused in Step 1

        payload = ok()
        with_context_warnings(payload, context_warnings=context.warnings)
        # Explicit warning for unhandled endpoint (helps extend coverage).
        payload["warnings"].append(
            {
                "code": "UNHANDLED_ENDPOINT",
                "message": "Request hit catch-all handler; endpoint not implemented yet.",
                "details": {
                    "method": request.method,
                    "path": f"/api/v1/{full_path}",
                    "query": dict(request.query_params),
                },
            }
        )

        return JSONResponse(payload, status_code=200)

    return app


app = create_app()
