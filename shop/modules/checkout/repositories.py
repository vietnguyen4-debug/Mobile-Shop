from typing import Optional

from bson import ObjectId

from .models import Checkout


ACTIVE_STATUSES = ("pending", "processing")


def checkout_create(data: dict) -> Checkout:
    checkout = Checkout(**data)
    return checkout.save()


def checkout_save(checkout: Checkout) -> Checkout:
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

