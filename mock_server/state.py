"""In-memory state store for the mock server.

Step 3 objective:
  - Keep mock state across calls (order/cart/air/etc.).
  - Auto-create entities when callers reference unknown IDs (never break flow).
  - Provide minimal but stable shapes for later steps to enrich.

This module intentionally avoids external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Mapping

from .headers import RequestContext
from .versioning import now_utc_iso


JsonObject = dict[str, Any]


@dataclass(slots=True)
class ConversationState:
    conversation_id: str
    application: str
    flow: str
    locale: str
    created_at: str = field(default_factory=now_utc_iso)
    updated_at: str = field(default_factory=now_utc_iso)


@dataclass(slots=True)
class OrderState:
    order_id: str
    conversation_id: str
    currency: str = "USD"
    status: str = "DRAFT"
    created_at: str = field(default_factory=now_utc_iso)
    updated_at: str = field(default_factory=now_utc_iso)
    revision: int = 0


@dataclass(slots=True)
class AirState:
    air_id: str
    order_id: str
    shopping_cart_id: str
    # Placeholder fields; later steps will fill flights/segments/options.
    segments: list[JsonObject] = field(default_factory=list)
    ancillaries: JsonObject = field(default_factory=dict)
    created_at: str = field(default_factory=now_utc_iso)
    updated_at: str = field(default_factory=now_utc_iso)
    revision: int = 0


@dataclass(slots=True)
class ShoppingCartState:
    shopping_cart_id: str
    order_id: str
    status: str = "OPEN"
    # Simplified representation; later steps will replace with contract-like payloads.
    selected_airs: list[str] = field(default_factory=list)
    travellers: list[JsonObject] = field(default_factory=list)
    customer: JsonObject = field(default_factory=dict)
    pricing: JsonObject = field(default_factory=dict)
    created_at: str = field(default_factory=now_utc_iso)
    updated_at: str = field(default_factory=now_utc_iso)
    revision: int = 0


@dataclass(slots=True)
class ProfileState:
    profile_id: str
    data: JsonObject = field(default_factory=dict)
    created_at: str = field(default_factory=now_utc_iso)
    updated_at: str = field(default_factory=now_utc_iso)


class MockStateStore:
    """Thread-safe in-memory store."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._global_revision = 0

        self.conversations: dict[str, ConversationState] = {}
        self.orders: dict[str, OrderState] = {}
        self.shopping_carts: dict[str, ShoppingCartState] = {}
        self.airs: dict[str, AirState] = {}
        self.profiles: dict[str, ProfileState] = {}

    def _bump_global(self) -> int:
        self._global_revision += 1
        return self._global_revision

    @property
    def global_revision(self) -> int:
        return self._global_revision

    def touch(self) -> int:
        """Bump global revision for any in-place state mutation."""

        with self._lock:
            return self._bump_global()

    def ensure_conversation(self, ctx: RequestContext) -> tuple[ConversationState, bool]:
        with self._lock:
            existing = self.conversations.get(ctx.conversation_id)
            if existing is not None:
                # Keep latest header-derived values but do not overwrite aggressively.
                existing.updated_at = now_utc_iso()
                return existing, False

            conv = ConversationState(
                conversation_id=ctx.conversation_id,
                application=ctx.application,
                flow=ctx.flow,
                locale=ctx.locale,
            )
            self.conversations[ctx.conversation_id] = conv
            self._bump_global()
            return conv, True

    def ensure_order(self, order_id: str, ctx: RequestContext) -> tuple[OrderState, bool]:
        with self._lock:
            existing = self.orders.get(order_id)
            if existing is not None:
                existing.updated_at = now_utc_iso()
                return existing, False

            order = OrderState(order_id=order_id, conversation_id=ctx.conversation_id)
            order.revision = self._bump_global()
            self.orders[order_id] = order
            return order, True

    def ensure_shopping_cart(self, order_id: str, shopping_cart_id: str) -> tuple[ShoppingCartState, bool]:
        with self._lock:
            existing = self.shopping_carts.get(shopping_cart_id)
            if existing is not None:
                existing.updated_at = now_utc_iso()
                return existing, False

            cart = ShoppingCartState(shopping_cart_id=shopping_cart_id, order_id=order_id)
            cart.revision = self._bump_global()
            self.shopping_carts[shopping_cart_id] = cart
            return cart, True

    def ensure_air(self, order_id: str, shopping_cart_id: str, air_id: str) -> tuple[AirState, bool]:
        with self._lock:
            existing = self.airs.get(air_id)
            if existing is not None:
                existing.updated_at = now_utc_iso()
                return existing, False

            air = AirState(air_id=air_id, order_id=order_id, shopping_cart_id=shopping_cart_id)
            air.revision = self._bump_global()
            self.airs[air_id] = air
            return air, True

    def ensure_profile(self, profile_id: str) -> tuple[ProfileState, bool]:
        with self._lock:
            existing = self.profiles.get(profile_id)
            if existing is not None:
                existing.updated_at = now_utc_iso()
                return existing, False

            profile = ProfileState(profile_id=profile_id)
            self.profiles[profile_id] = profile
            self._bump_global()
            return profile, True

    def ensure_from_request(
        self,
        *,
        ctx: RequestContext,
        path_params: Mapping[str, str],
    ) -> list[JsonObject]:
        """Ensure entities referenced by common path params exist.

        Returns warnings describing any auto-created entities.
        """

        warnings: list[JsonObject] = []

        # Conversation is always present (generated if missing).
        _, conv_created = self.ensure_conversation(ctx)
        if conv_created:
            warnings.append(
                {
                    "code": "AUTO_CREATED",
                    "message": "Conversation was auto-created by mock.",
                    "details": {"conversationId": ctx.conversation_id},
                }
            )

        # FastAPI/Starlette stores params exactly as in the route template.
        order_id = (path_params.get("orderId") or path_params.get("order_id") or "").strip()
        cart_id = (path_params.get("shoppingCartId") or path_params.get("shopping_cart_id") or "").strip()
        air_id = (path_params.get("airId") or path_params.get("air_id") or "").strip()
        profile_id = (path_params.get("profileId") or path_params.get("profile_id") or "").strip()

        if order_id:
            _, created = self.ensure_order(order_id, ctx)
            if created:
                warnings.append(
                    {
                        "code": "AUTO_CREATED",
                        "message": "Order was auto-created by mock.",
                        "details": {"orderId": order_id},
                    }
                )

        if order_id and cart_id:
            _, created = self.ensure_shopping_cart(order_id, cart_id)
            if created:
                warnings.append(
                    {
                        "code": "AUTO_CREATED",
                        "message": "Shopping cart was auto-created by mock.",
                        "details": {"orderId": order_id, "shoppingCartId": cart_id},
                    }
                )

        if order_id and cart_id and air_id:
            air, created = self.ensure_air(order_id, cart_id, air_id)
            # Maintain link from cart to selected airs for later steps.
            cart, _ = self.ensure_shopping_cart(order_id, cart_id)
            if air.air_id not in cart.selected_airs:
                cart.selected_airs.append(air.air_id)
                cart.revision = self._bump_global()
            if created:
                warnings.append(
                    {
                        "code": "AUTO_CREATED",
                        "message": "Air was auto-created by mock.",
                        "details": {"orderId": order_id, "shoppingCartId": cart_id, "airId": air_id},
                    }
                )

        if profile_id:
            _, created = self.ensure_profile(profile_id)
            if created:
                warnings.append(
                    {
                        "code": "AUTO_CREATED",
                        "message": "Profile was auto-created by mock.",
                        "details": {"profileId": profile_id},
                    }
                )

        return warnings
