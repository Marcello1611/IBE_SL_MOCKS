"""Small helpers for deterministic IDs and timestamps (mock-friendly).

Real backend uses various ID formats; the mock should be stable and predictable
unless the caller relies on uniqueness only.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"



def stable_id(prefix: str, seed: str, *, length: int = 12) -> str:
    """Deterministic ID generator based on a seed string.

    Notes:
      - Uses SHA-1 for compactness and determinism (not for security).
      - Output format: <prefix>-<hex[:length]>
    """

    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:length]}"
