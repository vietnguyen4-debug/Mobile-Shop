from typing import Dict, List

from ..cart.repositories import cart_save
from ..shipment.services import s_assign_shipment
from .repositories import checkout_save
from .mappers import checkout_snapshot, serialize_payments, serialize_shipment
from ...core.utils import *
from .service_helpers import (
    CustomerInfo,
    _collect_related_documents,
    _compute_cart_snapshot,
    _create_anonymous_user,
    _ensure_cart_user,
    _find_existing_checkout,
    _get_active_cart,
    _load_checkout,
    _parse_customer,
    _store_checkout,
    _update_shipment_status,
    _cancel_pending_payments,
    _build_virtual_shipment_snapshot
)


def _calculate_totals(
    subtotal: float, payments: List[Any], currency: Optional[str]
) -> Dict[str, float]:
    completed_total = 0.0
    pending_total = 0.0
    for payment in payments or []:
        amount = float(getattr(payment, "amount", 0.0) or 0.0)
        status = getattr(payment, "status", None)
        if status == "completed":
            completed_total += amount
        else:
            pending_total += amount
    outstanding = subtotal - completed_total
    if outstanding < 0:
        outstanding = 0.0
    return {
        "currency": currency or "VND",
        "subtotal": subtotal,
        "completed_payments": completed_total,
        "pending_payments": pending_total,
        "outstanding": outstanding,
    }


def _build_snapshot(checkout) -> Dict[str, Any]:
    cart = getattr(checkout, "cart", None)
    if cart:
        cart_data, subtotal = _compute_cart_snapshot(cart)
    else:
        cart_data, subtotal = None, float(getattr(checkout, "total_amount", 0.0) or 0.0)

    shipment_doc, payment_docs = _collect_related_documents(checkout)
    if shipment_doc:
        shipment_data = serialize_shipment(shipment_doc)
    else:
        shipment_data = _build_virtual_shipment_snapshot(checkout)
    payments_data = serialize_payments(payment_docs)
    totals = _calculate_totals(subtotal, payment_docs, getattr(checkout, "currency", "VND"))
    return checkout_snapshot(
        checkout,
        cart_data=cart_data,
        shipment_data=shipment_data,
        payments=payments_data,
        totals=totals,
    )


def _prepare_shipment_payload(
    checkout_id: str,
    session_id: Optional[str],
    user,
    shipment_payload: Optional[dict],
    customer: Optional[CustomerInfo],
) -> Optional[Tuple[dict, Optional[str]]]:
    payload = shipment_payload or {}
    if not shipment_payload and customer:
        full_name = f"{customer.first_name} {customer.last_name}".strip()
        payload = {
            "address": {
                "address_line": customer.address_line,
                "city": customer.city,
            },
            "recipient_name": full_name,
            "recipient_phone": customer.phone,
        }

    if not payload:
        return None

    payload = dict(payload)
    payload["checkout_id"] = checkout_id
    if session_id:
        payload.setdefault("session_id", session_id)
    payload_user_id = str(user.id) if user else None
    return payload, payload_user_id


def s_start_checkout(user_id: Optional[str], payload: Optional[dict]) -> Dict[str, Any]:
    payload = payload or {}
    try:
        session_id = sanitize_session_id(payload.get("session_id"))
        user = load_user(user_id)
        cart = _get_active_cart(user, session_id)

        if not user and getattr(cart, "user", None):
            user = cart.user

        customer: Optional[CustomerInfo] = None
        if not user:
            customer = _parse_customer(payload.get("customer"))
            user = _create_anonymous_user(customer)

        cart = _ensure_cart_user(cart, user, session_id)
        checkout = _find_existing_checkout(cart)
        _, subtotal = _compute_cart_snapshot(cart)
        checkout = _store_checkout(
            checkout,
            cart=cart,
            user=user,
            session_id=session_id,
            subtotal=subtotal,
        )

        shipment_payload = payload.get("shipment")
        prepared = _prepare_shipment_payload(
            str(checkout.id), session_id, user, shipment_payload, customer
        )
        if prepared:
            shipment_data, payload_user_id = prepared
            s_assign_shipment(payload_user_id, shipment_data)

        checkout.total_amount = subtotal
        checkout = checkout_save(checkout)
        return _build_snapshot(checkout)
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(f"Failed to initialize checkout: {str(exc)}", 500, name="DATABASE_ERROR")


def s_get_checkout(
    checkout_id: str, user_id: Optional[str], session_id: Optional[str]
) -> Dict[str, Any]:
    try:
        checkout = _load_checkout(checkout_id)
        user = load_user(user_id)
        sanitized_session = sanitize_session_id(session_id)
        ensure_checkout_access(checkout, user, sanitized_session)
        checkout = checkout_save(checkout)  # refresh expiration if near TTL
        return _build_snapshot(checkout)
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to retrieve checkout: {str(exc)}", 500, name="DATABASE_ERROR"
        )


def s_cancel_checkout(
    checkout_id: str, user_id: Optional[str], payload: Optional[dict]
) -> Dict[str, Any]:
    payload = payload or {}
    try:
        checkout = _load_checkout(checkout_id)
        user = load_user(user_id)
        session_id = sanitize_session_id(payload.get("session_id"))
        ensure_checkout_access(checkout, user, session_id)

        status = getattr(checkout, "status", None) or "pending"
        if status == "completed":
            raise AppError(
                "Cannot cancel a completed checkout", 400, name="CHECKOUT_COMPLETED"
            )
        shipment_doc, payment_docs = _collect_related_documents(checkout)
        if status == "cancelled":
            # Ensure related docs are also cancelled (idempotent).
            _update_shipment_status(shipment_doc, status="cancelled")
            _cancel_pending_payments(payment_docs)
            return _build_snapshot(checkout)

        # Disallow cancel if any payment is completed to avoid abuse.
        if any(getattr(payment, "status", None) == "completed" for payment in payment_docs):
            raise AppError(
                "Cannot cancel a checkout with completed payment",
                400,
                name="CHECKOUT_PAYMENT_COMPLETED",
            )

        # Disallow cancel if shipment already progressed beyond pending.
        if shipment_doc and getattr(shipment_doc, "status", None) in ("processing", "shipped", "delivered"):
            raise AppError(
                "Cannot cancel a checkout with shipment in progress",
                400,
                name="CHECKOUT_SHIPMENT_IN_PROGRESS",
            )

        _update_shipment_status(shipment_doc, status="cancelled")
        _cancel_pending_payments(payment_docs)

        checkout.status = "cancelled"
        checkout.user = user or checkout.user
        if session_id:
            checkout.session_id = session_id
        checkout = checkout_save(checkout)
        return _build_snapshot(checkout)
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to cancel checkout: {str(exc)}", 500, name="DATABASE_ERROR"
        )


def s_complete_checkout(
    checkout_id: str, user_id: Optional[str], payload: Optional[dict]
) -> Dict[str, Any]:
    payload = payload or {}
    try:
        checkout = _load_checkout(checkout_id)
        user = load_user(user_id)
        session_id = sanitize_session_id(payload.get("session_id"))
        ensure_checkout_access(checkout, user, session_id)

        status = getattr(checkout, "status", None) or "pending"
        if status == "cancelled":
            raise AppError(
                "Cannot complete a cancelled checkout",
                400,
                name="CHECKOUT_CANCELLED",
            )

        shipment_doc, payment_docs = _collect_related_documents(checkout)
        if not shipment_doc:
            raise AppError(
                "Shipment information is required before completing checkout",
                400,
                name="CHECKOUT_NO_SHIPMENT",
            )
        if not any(getattr(payment, "status", None) == "completed" for payment in payment_docs):
            raise AppError(
                "At least one completed payment is required to finish checkout",
                400,
                name="CHECKOUT_UNPAID",
            )

        _update_shipment_status(shipment_doc, status="processing")

        if getattr(checkout, "status", None) != "completed":
            cart = getattr(checkout, "cart", None)
            if cart:
                _, subtotal = _compute_cart_snapshot(cart)
            else:
                subtotal = float(getattr(checkout, "total_amount", 0.0) or 0.0)
            checkout.total_amount = subtotal
            checkout.status = "completed"
            checkout.user = user or checkout.user
            if session_id:
                checkout.session_id = session_id
            checkout = checkout_save(checkout)
            if cart:
                cart.status = "converted"
                cart_save(cart)

        return _build_snapshot(checkout)
    except AppError:
        raise
    except Exception as exc:  
        raise AppError(
            f"Failed to complete checkout: {str(exc)}", 500, name="DATABASE_ERROR"
        )
