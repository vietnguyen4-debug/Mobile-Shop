from typing import Optional
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from flask import current_app
from .models import Checkout


# Only pending checkouts carry TTL; processing/completed/cancelled have no TTL.
ACTIVE_STATUSES = ("pending",)

def _apply_expiration(checkout: Checkout) -> Checkout:
    ttl_seconds = current_app.config.get("CHECKOUT_PENDING_TTL_SECONDS")
    renew_threshold = current_app.config.get("CHECKOUT_TTL_RENEW_THRESHOLD_SECONDS", 0)
    if not ttl_seconds or ttl_seconds <= 0:
        checkout.expires_at = None
        return checkout

    status = getattr(checkout, "status", None)
    # Set TTL once for active checkouts; do not extend on every save to avoid
    # indefinite keep-alive via repeated POSTs. Terminal states clear TTL.
    if status in ACTIVE_STATUSES:
        expires_at = getattr(checkout, "expires_at", None)
        now = datetime.now(timezone.utc)
        if not expires_at:
            checkout.expires_at = now + timedelta(seconds=ttl_seconds)
        elif renew_threshold and expires_at <= now + timedelta(seconds=renew_threshold):
            # Renew when close to expiry and user is still interacting.
            checkout.expires_at = now + timedelta(seconds=ttl_seconds)
    else:
        checkout.expires_at = None
    return checkout

def checkout_create(data: dict) -> Checkout:
    checkout = Checkout(**data)
    checkout = _apply_expiration(checkout)
    return checkout.save()


def checkout_save(checkout: Checkout) -> Checkout:
    checkout = _apply_expiration(checkout)
    return checkout.save()


def checkout_get_by_id(checkout_id: str) -> Optional[Checkout]:
    try:
        oid = ObjectId(checkout_id)
    except Exception:
        return None
    return Checkout.objects(id=oid).first()


def checkout_get_active_by_user(user) -> Optional[Checkout]:
    if not user:
        return None
    return (
        Checkout.objects(user=user, status__in=ACTIVE_STATUSES)
        .order_by("-created_at")
        .first()
    )


def checkout_get_active_by_session(session_id: Optional[str]) -> Optional[Checkout]:
    if not session_id:
        return None
    cleaned = session_id.strip()
    if not cleaned:
        return None
    return (
        Checkout.objects(session_id=cleaned, status__in=ACTIVE_STATUSES)
        .order_by("-created_at")
        .first()
    )


def checkout_get_by_cart(cart) -> Optional[Checkout]:
    if not cart:
        return None
    return Checkout.objects(cart=cart).order_by("-created_at").first()
