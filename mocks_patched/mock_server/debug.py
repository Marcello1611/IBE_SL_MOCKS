"""Debug helpers.

The mock server can optionally include additional debug metadata in responses.
This is useful for local troubleshooting but may break strict API clients that
fail on unknown JSON properties.

Enable with:
  MOCK_DEBUG=1
"""

from __future__ import annotations

import os


def debug_enabled() -> bool:
    v = (os.getenv("MOCK_DEBUG") or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}
