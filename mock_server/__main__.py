"""Module entrypoint for the mock server.

This entrypoint is intentionally minimal and is used only to start the server.
All HTTP behavior is defined in mock_server.server.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("MOCK_HOST", "0.0.0.0")
    port = int(os.getenv("MOCK_PORT", "8080"))
    log_level = os.getenv("MOCK_LOG_LEVEL", "info").lower()

    uvicorn.run(
        "mock_server.server:app",
        host=host,
        port=port,
        log_level=log_level,
        # UI mocks are often run behind reverse proxies / tunnels.
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
