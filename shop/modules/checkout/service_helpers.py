from dataclasses import dataclass
from typing import Any, Optional, Tuple
from uuid import uuid4

from ...core.exceptions import AppError
from ...core.security import hash_password
from ..cart.mappers import cart_public
from ..cart.models import Cart
from ..cart.repositories import (
    cart_get_active_by_session,
    cart_get_active_by_user,
    cart_save,
)
from ..payment.repositories import payment_list_by_checkout, payment_save
from ..shipment.repositories import shipment_get_by_checkout, shipment_save
from ..users.models import Address, User
from .models import Checkout
from .repositories import checkout_create, checkout_get_by_cart, checkout_get_by_id, checkout_save
from ...core.utils import normalize_required_string


@dataclass
class CustomerInfo:
    first_name: str
    last_name: str
    phone: str
    address_line: str
    city: str

def _load_checkout(checkout_id: Any) -> Checkout:
    if checkout_id is None:
        raise AppError("Checkout identifier is required", 400, name="INVALID_CHECKOUT")
    checkout = checkout_get_by_id(str(checkout_id))
    if not checkout:
        raise AppError("Checkout not found", 404, name="CHECKOUT_NOT_FOUND")
    return checkout

def _get_active_cart(user: Optional[User], session_id: Optional[str]) -> Cart:
    try:
        cart = cart_get_active_by_user(user) if user else None
        if not cart and session_id:
            cart = cart_get_active_by_session(session_id)
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to load cart: {str(exc)}", 500, name="DATABASE_ERROR")

    if not cart:
        raise AppError("Cart not found", 404, name="INVALID_CART")
    if not cart.items:
        raise AppError("Cart is empty", 400, name="EMPTY_CART")
    return cart


def _ensure_cart_user(cart: Cart, user: User, session_id: Optional[str]) -> Cart:
    updated = False
    if user and (not getattr(cart, "user", None) or str(cart.user.id) != str(user.id)):
        cart.user = user
        updated = True
    if session_id and getattr(cart, "session_id", None) != session_id:
        cart.session_id = session_id
        updated = True
    if updated:
        try:
            cart = cart_save(cart)
        except Exception as exc:  # pragma: no cover - defensive
            raise AppError(f"Failed to save cart: {str(exc)}", 500, name="DATABASE_ERROR")
    return cart

def _parse_customer(payload: Any) -> CustomerInfo:
    if not isinstance(payload, dict):
        raise AppError("customer must be an object", 400, name="INVALID_CUSTOMER")
    first_name = normalize_required_string(
        payload.get("first_name"),
        field="First name",
        code="INVALID_FIRST_NAME",
        max_length=50,
    )
    last_name = normalize_required_string(
        payload.get("last_name"),
        field="Last name",
        code="INVALID_LAST_NAME",
        max_length=50,
    )
    phone = normalize_required_string(
        payload.get("phone"),
        field="Phone",
        code="INVALID_PHONE",
        max_length=30,
    )
    address_payload = payload.get("address")
    if not isinstance(address_payload, dict):
        raise AppError("address must be an object", 400, name="INVALID_ADDRESS")
    address_line = normalize_required_string(
        address_payload.get("address_line"),
        field="Address line",
        code="INVALID_ADDRESS_LINE",
        max_length=255,
    )
    city = normalize_required_string(
        address_payload.get("city"),
        field="City",
        code="INVALID_CITY",
        max_length=120,
    )
    return CustomerInfo(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        address_line=address_line,
        city=city,
    )


def _create_anonymous_user(customer: CustomerInfo) -> User:
    random_token = uuid4().hex
    password = hash_password(uuid4().hex)
    try:
        user = User(
            username=f"guest_{random_token}",
            email=f"guest_{random_token}@guest.local",
            password_hash=password,
            role="user",
            first_name=customer.first_name,
            last_name=customer.last_name,
            phone=customer.phone,
            is_active=False,
        )
        user.addresses = [
            Address(
                address_line=customer.address_line,
                city=customer.city,
                is_default=True,
            )
        ]
        user = user.save()
        return user
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to create guest user: {str(exc)}", 500, name="DATABASE_ERROR")


def _find_existing_checkout(cart: Cart) -> Optional[Checkout]:
    # Always create a fresh checkout for each start; do not reuse previous ones.
    return None


def _compute_cart_snapshot(cart: Cart) -> Tuple[dict, float]:
    try:
        cart_data = cart_public(cart)
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to serialize cart: {str(exc)}", 500, name="MAPPING_ERROR")
    subtotal = float(cart_data.get("subtotal") or 0.0)
    return cart_data, subtotal


def _store_checkout(
    checkout: Optional[Checkout],
    *,
    cart: Cart,
    user: Optional[User],
    session_id: Optional[str],
    subtotal: float,
) -> Checkout:
    if checkout:
        checkout.user = user
        checkout.session_id = session_id
        checkout.cart = cart
        checkout.total_amount = subtotal
        try:
            return checkout_save(checkout)
        except Exception as exc:  # pragma: no cover - defensive
            raise AppError(
                f"Failed to update checkout: {str(exc)}", 500, name="DATABASE_ERROR"
            )

    payload = {
        "cart": cart,
        "user": user,
        "session_id": session_id,
        "status": "pending",
        "currency": "VND",
        "total_amount": subtotal,
    }
    try:
        return checkout_create(payload)
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to create checkout: {str(exc)}", 500, name="DATABASE_ERROR")


def _collect_related_documents(checkout: Checkout):
    shipment = shipment_get_by_checkout(checkout)
    payments = payment_list_by_checkout(checkout)
    return shipment, payments


def _cancel_pending_payments(payments) -> int:
    """
    Cancel any non-completed payments (pending) to keep checkout cancellation consistent.
    Returns number of payments cancelled.
    """
    cancelled = 0
    for payment in payments or []:
        status = getattr(payment, "status", None)
        if status == "pending":
            payment.status = "cancelled"
            try:
                payment_save(payment)
                cancelled += 1
            except Exception as exc:  # pragma: no cover - defensive
                raise AppError(
                    f"Failed to cancel payment: {str(exc)}", 500, name="DATABASE_ERROR"
                )
    return cancelled

def _get_default_user_address(user: Optional[User]) -> Optional[Address]:
    if not user:
        return None
    addresses = getattr(user, "addresses", None) or []
    for address in addresses:
        if getattr(address, "is_default", False):
            return address
    return None


def _build_virtual_shipment_snapshot(checkout: Checkout) -> Optional[dict]:
    user = getattr(checkout, "user", None)
    if not user:
        return None

    address = _get_default_user_address(user)
    if not address:
        return None

    first_name = getattr(user, "first_name", "") or ""
    last_name = getattr(user, "last_name", "") or ""
    full_name = " ".join(part for part in [first_name, last_name] if part).strip() or None

    return {
        "id": None,
        "checkout_id": str(checkout.id) if getattr(checkout, "id", None) else None,
        "user_id": str(user.id) if getattr(user, "id", None) else None,
        "session_id": getattr(checkout, "session_id", None),
        "source": "user",
        "status": getattr(checkout, "status", None) or "pending",
        "address_line": getattr(address, "address_line", None),
        "city": getattr(address, "city", None),
        "recipient_name": full_name,
        "recipient_phone": getattr(user, "phone", None),
        "note": None,
        "user_address_id": getattr(address, "id", None),
        "created_at": None,
        "updated_at": None,
        "__virtual__": True,
    }

def _update_shipment_status(shipment, *, status: str) -> None:
    if not shipment:
        return
    if getattr(shipment, "status", None) == status:
        return
    shipment.status = status
    try:
        shipment_save(shipment)
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to update shipment status: {str(exc)}", 500, name="DATABASE_ERROR"
        )
