from typing import Any, Dict, List, Optional

from ...core.exceptions import AppError
from ..cart.mappers import cart_public
from ..payment.mappers import payment_public
from ..shipment.mappers import shipment_public


def _checkout_user_public(checkout) -> Dict[str, Any]:
    return {
        "id": str(checkout.id),
        "cart_id": str(checkout.cart.id) if getattr(checkout, "cart", None) else None,
        "user_id": str(checkout.user.id),
        "status": getattr(checkout, "status", None),
        "currency": getattr(checkout, "currency", "VND"),
        "total_amount": float(getattr(checkout, "total_amount", 0.0) or 0.0),
    }


def _checkout_guest_public(checkout) -> Dict[str, Any]:
    return {
        "id": str(checkout.id),
        "cart_id": str(checkout.cart.id) if getattr(checkout, "cart", None) else None,
        "session_id": getattr(checkout, "session_id", None),
        "status": getattr(checkout, "status", None),
        "currency": getattr(checkout, "currency", "VND"),
        "total_amount": float(getattr(checkout, "total_amount", 0.0) or 0.0),
    }


def checkout_public(checkout) -> Optional[Dict[str, Any]]:
    try:
        if not checkout:
            return None
        user = getattr(checkout, "user", None)
        session_id = getattr(checkout, "session_id", None)
        is_guest = bool(session_id) and (user is None or not getattr(user, "is_active", True))
        if user and not is_guest:
            return _checkout_user_public(checkout)
        return _checkout_guest_public(checkout)
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to map checkout: {str(exc)}", 500, name="MAPPING_ERROR")


def checkout_snapshot(
    checkout,
    *,
    cart_data: Optional[Dict[str, Any]],
    shipment_data: Optional[Dict[str, Any]],
    payments: List[Dict[str, Any]],
    totals: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        return {
            "checkout": checkout_public(checkout),
            "cart": cart_data,
            "shipment": shipment_data,
            "payments": payments,
            "totals": totals,
        }
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to map checkout snapshot: {str(exc)}", 500, name="MAPPING_ERROR"
        )


def serialize_cart(cart, *, user=None) -> Optional[Dict[str, Any]]:
    if not cart:
        return None
    return cart_public(cart)


def serialize_shipment(shipment) -> Optional[Dict[str, Any]]:
    return shipment_public(shipment)


def serialize_payments(payments) -> List[Dict[str, Any]]:
    return [payment_public(payment) for payment in payments or []]
