"""Celery tasks for background maintenance."""

from datetime import datetime, timezone

from shop.tasks import celery
from shop.modules.cart.repositories import cart_delete, cart_list_expired_guest_active
from shop.modules.checkout.models import Checkout
from shop.modules.checkout.repositories import ACTIVE_STATUSES
from shop.modules.checkout.service_helpers import (
    _collect_related_documents,
    _update_shipment_status,
    _cancel_pending_payments,
)


@celery.task(name="tasks.cancel_expired_checkouts")
def cancel_expired_checkouts(limit: int = 100) -> dict:
    """
    Mark expired checkouts as cancelled instead of letting TTL delete them.
    Returns a summary dict with the number cancelled.
    """
    now = datetime.now(timezone.utc)
    stale_qs = Checkout.objects(
        status__in=ACTIVE_STATUSES, expires_at__lte=now
    ).limit(limit)

    cancelled = 0
    for checkout in stale_qs:
        shipment, payments = _collect_related_documents(checkout)
        # Best-effort: cancel any pending payments attached to this checkout.
        try:
            _cancel_pending_payments(payments)
        except Exception:
            pass
        _update_shipment_status(shipment, status="cancelled")
        checkout.status = "cancelled"
        checkout.expires_at = None
        checkout.save()
        cancelled += 1

    return {"cancelled": cancelled}


@celery.task(name="tasks.expire_guest_carts")
def expire_guest_carts(limit: int = 200) -> dict:
    """
    Delete expired guest carts based on server-side guest TTL policy.
    """
    expired_carts = cart_list_expired_guest_active(limit=int(limit))

    deleted = 0
    errors = 0
    for cart in expired_carts:
        try:
            cart_delete(cart)
            deleted += 1
        except Exception:
            errors += 1

    return {"deleted": deleted, "errors": errors}


__all__ = ["cancel_expired_checkouts", "expire_guest_carts"]
