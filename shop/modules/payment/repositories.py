from typing import List, Optional

from bson import ObjectId

from .models import Payment
from datetime import datetime


def payment_create(data: dict) -> Payment:
    payment = Payment(**data)
    return payment.save()


def payment_get_by_id(payment_id: str) -> Optional[Payment]:
    try:
        oid = ObjectId(payment_id)
    except Exception:
        return None
    return Payment.objects(id=oid).first()


def payment_get_by_provider_ref(provider_ref: str) -> Optional[Payment]:
    if not provider_ref:
        return None
    return Payment.objects(provider_ref=provider_ref).order_by("-created_at").first()


def payment_save(payment: Payment) -> Payment:
    return payment.save()


def payment_list_by_checkout(checkout) -> List[Payment]:
    return list(Payment.objects(checkout=checkout).order_by("-created_at"))


def payment_list_pending_vnpay(*, before=None, limit: int = 100) -> List[Payment]:
    qs = Payment.objects(status="pending", provider="vnpay").order_by("created_at")
    if before is not None:
        qs = qs.filter(created_at__lte=before)
    return list(qs.limit(limit))


def payment_list_pending_by_provider(
    *,
    provider: str,
    method: str | None = None,
    before: datetime | None = None,
    limit: int = 100,
) -> List[Payment]:
    qs = Payment.objects(status="pending", provider=provider)
    if method:
        qs = qs.filter(method=method)
    if before:
        qs = qs.filter(created_at__lte=before)
    return list(qs.order_by("created_at").limit(limit))
