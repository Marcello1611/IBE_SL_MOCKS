"""Response envelope helpers.

The real backend typically returns an object that includes:
  - error (or null)
  - warnings (list)
  - rules (list or object)
  - banners (list)
plus a payload that varies by endpoint.

For maximum compatibility with existing UIs, payload keys are merged into the
top-level response object (instead of nesting under a "payload" key).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping


JsonObject = dict[str, Any]


@dataclass(slots=True)
class BaseResponse:
    """A minimal response representation used by the mock.

    This class is intentionally small and serialization-friendly.
    """

    error: JsonObject | None = None
    warnings: list[JsonObject] | None = None
    rules: list[Any] | None = None
    banners: list[JsonObject] | None = None

    def to_dict(self, payload: Mapping[str, Any] | None = None) -> JsonObject:
        out: JsonObject = {
            "error": self.error,
            "warnings": self.warnings if self.warnings is not None else [],
            "rules": self.rules if self.rules is not None else [],
            "banners": self.banners if self.banners is not None else [],
        }
        if payload:
            out.update(dict(payload))
        return out


def _ensure_list(value: Iterable[Any] | None) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return list(value)


def ok(
    payload: Mapping[str, Any] | None = None,
    *,
    warnings: Iterable[JsonObject] | None = None,
    rules: Iterable[Any] | None = None,
    banners: Iterable[JsonObject] | None = None,
) -> JsonObject:
    """Build a successful response."""

    return BaseResponse(
        error=None,
        warnings=_ensure_list(warnings),
        rules=_ensure_list(rules),
        banners=_ensure_list(banners),
    ).to_dict(payload=payload)


def fail(
    error: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
    *,
    warnings: Iterable[JsonObject] | None = None,
    rules: Iterable[Any] | None = None,
    banners: Iterable[JsonObject] | None = None,
) -> JsonObject:
    """Build a response with an error envelope."""

    return BaseResponse(
        error=dict(error),
        warnings=_ensure_list(warnings),
        rules=_ensure_list(rules),
        banners=_ensure_list(banners),
    ).to_dict(payload=payload)


def merge_warning(
    response: MutableMapping[str, Any],
    warning: Mapping[str, Any],
) -> None:
    """Append a warning to a response dict in a safe way."""

    warnings = response.get("warnings")
    if warnings is None:
        response["warnings"] = [dict(warning)]
        return
    if not isinstance(warnings, list):
        response["warnings"] = [warnings, dict(warning)]
        return
    warnings.append(dict(warning))


def with_context_warnings(
    response: MutableMapping[str, Any],
    *,
    context_warnings: Iterable[Mapping[str, Any]] | None,
) -> MutableMapping[str, Any]:
    """Merge context warnings into the response."""

    if not context_warnings:
        return response
    for w in context_warnings:
        merge_warning(response, w)
    return response
