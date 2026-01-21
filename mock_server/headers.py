"""Header normalization utilities.

Real API relies heavily on request headers (application/flow/locale/conversation).
The mock must be lenient: missing headers should not break UI flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from uuid import uuid4


APPLICATION = "X-Application"
FLOW = "X-Flow"
LOCALE = "X-Locale"
CONVERSATION = "X-Conversation"

DEFAULT_APPLICATION = "IBE"
DEFAULT_FLOW = "revenue"
DEFAULT_LOCALE = "en"


def _lower_map(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in headers.items()}


@dataclass(slots=True)
class RequestContext:
    """Normalized request context derived from headers.

    - conversation_id: generated if missing
    - warnings: always a list of dicts (stable JSON shape)
    """

    application: str
    flow: str
    locale: str
    conversation_id: str
    warnings: list[dict]

    def as_dict(self) -> dict:
        return {
            "application": self.application,
            "flow": self.flow,
            "locale": self.locale,
            "conversationId": self.conversation_id,
        }


def build_request_context(headers: Mapping[str, str]) -> RequestContext:
    """Build a normalized RequestContext from incoming headers.

    Policy:
    - Always succeeds.
    - Missing or empty headers are replaced by defaults and produce warnings.
    """

    h = _lower_map(headers)
    warnings: list[dict] = []

    def get(name: str, default: str | None) -> str:
        key = name.lower()
        value = h.get(key, "").strip()
        if value:
            return value
        if default is None:
            return ""
        warnings.append(
            {
                "code": "MISSING_HEADER",
                "message": f"Header {name} is missing; mock applied a default.",
                "details": {"header": name, "default": default},
            }
        )
        return default

    application = get(APPLICATION, DEFAULT_APPLICATION)
    flow = get(FLOW, DEFAULT_FLOW)
    locale = get(LOCALE, DEFAULT_LOCALE)

    conversation = h.get(CONVERSATION.lower(), "").strip()
    if not conversation:
        conversation = f"mock-{uuid4().hex}"
        warnings.append(
            {
                "code": "MISSING_HEADER",
                "message": f"Header {CONVERSATION} is missing; mock generated a value.",
                "details": {"header": CONVERSATION, "generated": True},
            }
        )

    return RequestContext(
        application=application,
        flow=flow,
        locale=locale,
        conversation_id=conversation,
        warnings=warnings,
    )
