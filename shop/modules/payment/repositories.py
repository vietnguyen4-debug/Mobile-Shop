from typing import List, Optional

from bson import ObjectId

from .models import Payment


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
