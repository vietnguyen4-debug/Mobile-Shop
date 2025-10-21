from typing import Optional

from .models import Cart


def cart_get_active_by_user(user) -> Optional[Cart]:
    if not user:
        return None
    return Cart.objects(user=user, status="active").first()


def cart_get_active_by_session(session_id: str) -> Optional[Cart]:
    if not session_id:
        return None
    return Cart.objects(session_id=session_id, status="active").first()


def cart_create(data: dict) -> Cart:
    return Cart(**data).save()


def cart_save(cart: Cart) -> Cart:
    return cart.save()


def cart_delete(cart: Cart) -> None:
    cart.delete()