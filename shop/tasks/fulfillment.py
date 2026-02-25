"""Celery tasks for fulfillment workflow (internal operations)."""

import logging

from shop.tasks import celery
from shop.tasks.locks import redis_lock
from shop.modules.payment.repositories import payment_get_by_id
from shop.modules.payment.services import _ensure_pending_shipment_for_checkout


_logger = logging.getLogger("shop.fulfillment")


@celery.task(name="tasks.on_payment_completed")
def on_payment_completed(payment_id: str) -> dict:
    """
    Idempotent hook invoked after a payment is marked completed.
    Keeps follow-up work out of the request path and allows scaling workers.
    """
    if not payment_id:
        return {"ok": False, "error": "missing payment_id"}

    lock_key = f"lock:payment_completed:{payment_id}"
    with redis_lock(lock_key, ttl_seconds=120) as acquired:
        if not acquired:
            return {"ok": True, "skipped": "locked"}

        payment = payment_get_by_id(payment_id)
        if not payment:
            return {"ok": False, "error": "payment_not_found"}

        if getattr(payment, "status", None) != "completed":
            return {"ok": True, "skipped": "payment_not_completed"}

        checkout = getattr(payment, "checkout", None)
        try:
            _ensure_pending_shipment_for_checkout(checkout)
        except Exception:
            _logger.exception(
                "Fulfillment failed to ensure shipment",
                extra={"payment_id": str(getattr(payment, "id", "")), "checkout_id": str(getattr(checkout, "id", ""))},
            )
            return {"ok": False, "error": "ensure_shipment_failed"}

        _logger.info(
            "Fulfillment processed payment completed",
            extra={
                "payment_id": str(getattr(payment, "id", "")),
                "checkout_id": str(getattr(checkout, "id", "")) if checkout else None,
            },
        )
        return {"ok": True}


__all__ = ["on_payment_completed"]

