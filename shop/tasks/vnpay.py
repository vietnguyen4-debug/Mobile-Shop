"""Celery tasks for VNPAY reconciliation."""

from shop.tasks import celery
from shop.modules.payment.services import s_reconcile_pending_vnpay_payments
from flask import current_app


@celery.task(name="tasks.reconcile_pending_vnpay_payments")
def reconcile_pending_vnpay_payments(limit: int = 100) -> dict:
    """
    Periodically query VNPAY (QueryDR) for pending payments that might have
    missed IPN/return callbacks.
    """
    min_age = int(current_app.config.get("VNPAY_RECONCILE_MIN_AGE_SECONDS", 300))
    return s_reconcile_pending_vnpay_payments(limit=int(limit), min_age_seconds=min_age)


__all__ = ["reconcile_pending_vnpay_payments"]

