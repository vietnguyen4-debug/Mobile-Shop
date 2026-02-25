from typing import Optional
from datetime import datetime, timedelta, timezone

from flask import current_app
from .models import Cart


def _guest_idle_ttl_seconds() -> int:
    return int(current_app.config.get("CART_GUEST_IDLE_TTL_SECONDS", 30 * 24 * 60 * 60) or 0)


def _guest_absolute_ttl_seconds() -> int:
    return int(current_app.config.get("CART_GUEST_ABSOLUTE_TTL_SECONDS", 90 * 24 * 60 * 60) or 0)


def _is_guest_cart(cart: Optional[Cart]) -> bool:
    return bool(cart and not getattr(cart, "user", None) and getattr(cart, "session_id", None))


def _guest_cart_is_expired(cart: Optional[Cart], *, now: datetime | None = None) -> bool:
    if not _is_guest_cart(cart):
        return False

    now = now or datetime.now(timezone.utc)

    guest_expires_at = getattr(cart, "guest_expires_at", None)
    if guest_expires_at:
        if guest_expires_at.tzinfo is None:
            guest_expires_at = guest_expires_at.replace(tzinfo=timezone.utc)
        if guest_expires_at <= now:
            return True
    else:
        # Backward compatibility: for carts created before guest_expires_at existed,
        # fall back to idle TTL based on last update time.
        idle_ttl = _guest_idle_ttl_seconds()
        if idle_ttl > 0:
            touched_at = getattr(cart, "updated_at", None) or getattr(cart, "created_at", None)
            if touched_at:
                if touched_at.tzinfo is None:
                    touched_at = touched_at.replace(tzinfo=timezone.utc)
                if touched_at + timedelta(seconds=idle_ttl) <= now:
                    return True

    absolute_ttl = _guest_absolute_ttl_seconds()
    if absolute_ttl > 0:
        created_at = getattr(cart, "created_at", None)
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at + timedelta(seconds=absolute_ttl) <= now:
                return True

    return False


def _apply_guest_expiration(cart: Cart) -> Cart:
    """
    Apply guest cart idle expiration on writes. Reads must not refresh the expiry.
    """
    if not _is_guest_cart(cart):
        cart.guest_expires_at = None
        return cart

    idle_ttl = _guest_idle_ttl_seconds()
    if idle_ttl <= 0:
        cart.guest_expires_at = None
        return cart

    cart.guest_expires_at = datetime.now(timezone.utc) + timedelta(seconds=idle_ttl)
    return cart


def cart_get_active_by_user(user) -> Optional[Cart]:
    if not user:
        return None
    return Cart.objects(user=user, status="active").first()


def cart_get_active_by_session(session_id: str) -> Optional[Cart]:
    if not session_id:
        return None
    cart = (
        Cart.objects(session_id=session_id, status="active")
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if _guest_cart_is_expired(cart):
        return None
    return cart


def cart_create(data: dict) -> Cart:
    cart = Cart(**data)
    cart = _apply_guest_expiration(cart)
    return cart.save()


def cart_save(cart: Cart) -> Cart:
    cart = _apply_guest_expiration(cart)
    return cart.save()


def cart_delete(cart: Cart) -> None:
    cart.delete()


def cart_list_expired_guest_active(*, now: datetime | None = None, limit: int = 200) -> list[Cart]:
    now = now or datetime.now(timezone.utc)
    carts_by_id: dict[str, Cart] = {}

    for cart in Cart.objects(user=None, status="active", guest_expires_at__lte=now).limit(limit):
        carts_by_id[str(cart.id)] = cart

    idle_ttl = _guest_idle_ttl_seconds()
    if idle_ttl > 0 and len(carts_by_id) < limit:
        cutoff = now - timedelta(seconds=idle_ttl)
        remaining = max(int(limit) - len(carts_by_id), 0)
        if remaining > 0:
            for cart in Cart.objects(user=None, status="active", guest_expires_at=None, updated_at__lte=cutoff).limit(remaining):
                carts_by_id.setdefault(str(cart.id), cart)

    absolute_ttl = _guest_absolute_ttl_seconds()
    if absolute_ttl > 0 and len(carts_by_id) < limit:
        cutoff = now - timedelta(seconds=absolute_ttl)
        remaining = max(int(limit) - len(carts_by_id), 0)
        if remaining > 0:
            for cart in Cart.objects(user=None, status="active", created_at__lte=cutoff).limit(remaining):
                carts_by_id.setdefault(str(cart.id), cart)

    carts = list(carts_by_id.values())
    carts.sort(key=lambda c: getattr(c, "updated_at", None) or getattr(c, "created_at", None) or now)
    return carts[: int(limit)]
