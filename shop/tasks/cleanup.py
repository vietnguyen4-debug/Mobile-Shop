"""Celery tasks for background maintenance."""

from datetime import datetime, timezone

from shop.tasks import celery
from shop.modules.checkout.models import Checkout
from shop.modules.checkout.repositories import ACTIVE_STATUSES
from shop.modules.checkout.service_helpers import (
    _collect_related_documents,
    _update_shipment_status,
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
        shipment, _ = _collect_related_documents(checkout)
        _update_shipment_status(shipment, status="cancelled")
        checkout.status = "cancelled"
        checkout.expires_at = None
        checkout.save()
        cancelled += 1

    return {"cancelled": cancelled}


__all__ = ["cancel_expired_checkouts"]
