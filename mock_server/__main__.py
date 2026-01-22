"""Module entrypoint for the mock server.

This entrypoint starts:
- the FastAPI/uvicorn server
- optionally, an ngrok tunnel (when MOCK_NGROK=1)

Ngrok requirements:
- ngrok must be installed and available in PATH
- NGROK_AUTHTOKEN should be configured if your ngrok plan requires it
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn


def _truthy(value: str | None) -> bool:
    v = (value or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _maybe_start_ngrok(port: int) -> None:
    """Start ngrok as a sidecar process if enabled via env."""

    if not _truthy(os.getenv("MOCK_NGROK")) and not _truthy(os.getenv("MOCK_ENABLE_NGROK")):
        return

    # Launch ngrok in the background.
    try:
        subprocess.Popen(
            ["ngrok", "http", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print("[mock] ngrok binary not found in PATH; tunnel was not started.", file=sys.stderr)
        return
    except Exception as exc:  # noqa: BLE001
        print(f"[mock] failed to start ngrok: {exc}", file=sys.stderr)
        return

    # Best-effort: print public URL (ngrok exposes local API at 4040 by default).
    for _ in range(50):
        try:
            with urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1) as resp:
                data = json.load(resp)
            tunnels = data.get("tunnels") or []
            for t in tunnels:
                public_url = t.get("public_url")
                if isinstance(public_url, str) and public_url:
                    print(f"[mock] ngrok tunnel: {public_url}", file=sys.stderr)
                    return
        except URLError:
            time.sleep(0.1)
        except Exception:  # noqa: BLE001
            time.sleep(0.1)


def main() -> None:
    host = os.getenv("MOCK_HOST", "0.0.0.0")
    port = int(os.getenv("MOCK_PORT", "8080"))
    log_level = os.getenv("MOCK_LOG_LEVEL", "info").lower()

    _maybe_start_ngrok(port)

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
