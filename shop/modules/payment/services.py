from typing import Optional
import os
import logging

from .service_helpers import (
    _parse_amount,
    _normalize_currency,
    _parse_paid_at,
    _build_vnpay_payment_url,
    _vnpay_hash,
)
from ...core.validation import require_fields
from .repositories import *
from .mappers import payment_public, payment_summary
from ...core.utils import (
    AppError,
    ensure_checkout_access,
    load_checkout,
    load_user,
    sanitize_session_id,
)
from ..checkout.repositories import checkout_save
from datetime import datetime, timezone


_vnp_logger = logging.getLogger("shop.payment.vnpay")


def _cancel_other_pending_payments(current_payment):
    """
    Cancel any other pending payments for the same checkout to prevent overpay.
    """
    try:
        checkout = getattr(current_payment, "checkout", None)
        if not checkout:
            return
        current_id = str(getattr(current_payment, "id", ""))
        for other in payment_list_by_checkout(checkout):
            if str(getattr(other, "id", "")) == current_id:
                continue
            if getattr(other, "status", None) == "pending":
                other.status = "cancelled"
                payment_save(other)
    except Exception:
        # Defensive: do not fail main payment flow if cleanup fails.
        pass

def _create_payment(user_id: str | None, payload: dict, *, method: str, require_access: bool) -> dict:
    amount_override = payload.pop("_amount_override", None)
    if amount_override is None:
        require_fields(payload, "checkout_id", "amount")
    else:
        require_fields(payload, "checkout_id")
    try:
        checkout = load_checkout(payload.get("checkout_id"))
        user = load_user(user_id)
        amount = amount_override if amount_override is not None else _parse_amount(payload.get("amount"))
        currency = _normalize_currency(payload.get("currency")) if amount_override is None else getattr(checkout, "currency", "VND")
        note = payload.get("note")
        if note is not None and not isinstance(note, str):
            raise AppError("Note must be a string", 400, name="INVALID_NOTE")
        cleaned_note = note.strip() if isinstance(note, str) else None
        session_id = sanitize_session_id(payload.get("session_id"))

        if require_access:
            ensure_checkout_access(checkout, user, session_id)

        provider = payload.get("provider")
        provider_ref = payload.get("provider_ref")

        payment = payment_create(
            {
                "checkout": checkout,
                "user": user,
                "session_id": session_id,
                "method": method,
                "provider": provider.strip() if isinstance(provider, str) else None,
                "provider_ref": provider_ref.strip() if isinstance(provider_ref, str) else None,
                "amount": amount,
                "currency": currency,
                "status": "pending",
                "note": cleaned_note,
            }
        )
        if not provider_ref:
            payment.provider_ref = str(payment.id)
            payment = payment_save(payment)
        # Mark checkout as processing once a payment attempt is created.
        if getattr(checkout, "status", None) not in ("completed", "cancelled"):
            checkout.status = "processing"
            if session_id:
                checkout.session_id = session_id
            # Ensure TTL is cleared when moving out of pending.
            if getattr(checkout, "expires_at", None):
                checkout.expires_at = None
            checkout = checkout_save(checkout)

        return payment_public(payment)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            f"Failed to create {method} payment: {str(exc)}",
            500,
            name="DATABASE_ERROR",
        )


def s_create_offline_payment(user_id: str | None, payload: dict) -> dict:
    # Admin-only route uses this; no checkout access enforcement.
    return _create_payment(user_id, payload, method="offline", require_access=False)


def s_create_online_payment(user_id: str | None, payload: dict) -> dict:
    # User-facing; ensure session/user can access checkout and force amount = outstanding.
    require_fields(payload, "checkout_id")
    checkout = load_checkout(payload.get("checkout_id"))
    user = load_user(user_id)
    session_id = sanitize_session_id(payload.get("session_id"))
    ensure_checkout_access(checkout, user, session_id)

    payments = payment_list_by_checkout(checkout)
    completed_total = sum(float(getattr(p, "amount", 0) or 0) for p in payments if getattr(p, "status", None) == "completed")
    total_amount = float(getattr(checkout, "total_amount", 0) or 0)
    outstanding = max(total_amount - completed_total, 0.0)
    if outstanding <= 0:
        raise AppError("Checkout already paid", 400, name="CHECKOUT_PAID")

    # Prevent multiple online payments pending at the same time to avoid overpay.
    if any(
        getattr(p, "status", None) == "pending"
        and getattr(p, "method", None) == "online"
        for p in payments
    ):
        raise AppError(
            "An online payment is already pending for this checkout",
            400,
            name="PAYMENT_PENDING_EXISTS",
        )

    provider = payload.get("provider")
    note = payload.get("note")

    data = {
        "checkout_id": str(checkout.id),
        "session_id": session_id,
        "provider": provider,
        "note": note,
        "_amount_override": outstanding,
    }
    # Use checkout currency when forcing amount.
    data["currency"] = getattr(checkout, "currency", "VND")

    payment = _create_payment(user_id, data, method="online", require_access=False)
    payment_url = _build_vnpay_payment_url(payment)
    if payment_url:
        payment["payment_url"] = payment_url
    return payment


def s_complete_payment(payment_id: str, payload: Optional[dict]) -> dict:
    payload = payload or {}
    try:
        payment = payment_get_by_id(payment_id)
        if not payment:
            raise AppError("Payment not found", 404, name="PAYMENT_NOT_FOUND")

        note = payload.get("note")
        if note is not None and not isinstance(note, str):
            raise AppError("Note must be a string", 400, name="INVALID_NOTE")

        if payment.status == "completed":
            if note is not None:
                payment.note = note.strip() or None
                payment = payment_save(payment)
            return payment_public(payment)

        payment.status = "completed"
        payment.paid_at = _parse_paid_at(payload.get("paid_at"))
        if note is not None:
            payment.note = note.strip() or None
        provider_ref = payload.get("provider_ref")
        if provider_ref is not None:
            payment.provider_ref = provider_ref.strip() or None
        payment = payment_save(payment)
        _cancel_other_pending_payments(payment)
        return payment_public(payment)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Failed to complete payment: {str(exc)}", 500, name="DATABASE_ERROR")


def s_handle_vnpay_webhook(params: dict):
    """
    Handle VNPAY IPN/return. Returns (body, status_code) tuple.
    """
    secret = os.environ.get("VNPAY_SECRET_KEY", "")
    if not secret:
        _vnp_logger.error("VNPAY secret not configured; rejecting webhook")
        return ({"RspCode": "99", "Message": "Secret not configured"}, 200)

    # Debug log all incoming params to help diagnose response codes.
    _vnp_logger.info("VNPAY webhook received", extra={"params": dict(params)})

    received_hash = (params.get("vnp_SecureHash") or "").upper()
    expected_hash = _vnpay_hash(params, secret)
    _vnp_logger.debug(
        "VNPAY webhook hash debug",
        extra={"received_hash": received_hash, "expected_hash": expected_hash},
    )
    if received_hash != expected_hash:
        _vnp_logger.warning(
            "VNPAY webhook invalid signature",
            extra={"received_hash": received_hash, "expected_hash": expected_hash},
        )
        return ({"RspCode": "97", "Message": "Invalid signature"}, 200)

    txn_ref = params.get("vnp_TxnRef")
    amount_param = params.get("vnp_Amount")
    pay_date = params.get("vnp_PayDate")
    rsp_code = params.get("vnp_ResponseCode")

    payment = payment_get_by_provider_ref(txn_ref)
    if not payment or getattr(payment, "status", None) == "cancelled":
        _vnp_logger.warning(
            "VNPAY webhook payment not found or cancelled",
            extra={"txn_ref": txn_ref, "rsp_code": rsp_code},
        )
        return ({"RspCode": "01", "Message": "Order not found"}, 200)

    try:
        amount = float(amount_param) / 100.0 if amount_param is not None else 0.0
    except Exception:
        _vnp_logger.exception(
            "VNPAY webhook failed to parse amount",
            extra={"amount_param": amount_param, "txn_ref": txn_ref},
        )
        amount = 0.0

    if amount <= 0 or abs(amount - float(payment.amount)) > 1e-6:
        _vnp_logger.warning(
            "VNPAY webhook amount mismatch",
            extra={
                "amount_param": amount_param,
                "parsed_amount": amount,
                "expected_amount": float(payment.amount),
                "txn_ref": txn_ref,
                "rsp_code": rsp_code,
            },
        )
        return ({"RspCode": "04", "Message": "Invalid amount"}, 200)

    if payment.status != "completed":
        payment.status = "completed"
        if pay_date:
            try:
                payment.paid_at = datetime.strptime(pay_date, "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                )
            except Exception:
                payment.paid_at = datetime.now(timezone.utc)
        else:
            payment.paid_at = datetime.now(timezone.utc)
        payment.provider = "vnpay"
        payment.provider_ref = txn_ref
        payment_save(payment)

        _cancel_other_pending_payments(payment)
        _vnp_logger.info(
            "VNPAY payment marked completed",
            extra={
                "payment_id": str(getattr(payment, "id", "")),
                "txn_ref": txn_ref,
                "amount": amount,
                "rsp_code": rsp_code,
                "pay_date": pay_date,
            },
        )

    # If vnp_ResponseCode is provided, echo it back for debugging; otherwise return 00.
    rsp_code = rsp_code or "00"
    message = "OK" if rsp_code == "00" else f"VNPAY ResponseCode={rsp_code}"
    _vnp_logger.info(
        "VNPAY webhook response",
        extra={"RspCode": rsp_code, "Message": message, "txn_ref": txn_ref},
    )
    return ({"RspCode": rsp_code, "Message": message}, 200)


def s_get_payment(payment_id: str, user_id: Optional[str], session_id: Optional[str]) -> dict:
    try:
        payment = payment_get_by_id(payment_id)
        if not payment:
            raise AppError("Payment not found", 404, name="PAYMENT_NOT_FOUND")
        checkout = getattr(payment, "checkout", None)
        if not checkout:
            raise AppError("Checkout not found for payment", 404, name="CHECKOUT_NOT_FOUND")
        user = load_user(user_id)
        sanitized_session = sanitize_session_id(session_id)
        ensure_checkout_access(checkout, user, sanitized_session)
        return payment_public(payment)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Failed to retrieve payment: {str(exc)}", 500, name="DATABASE_ERROR")


def s_list_payments_by_checkout(user_id: Optional[str], session_id: Optional[str], checkout_id: str) -> list[dict]:
    try:
        checkout = load_checkout(checkout_id)
        user = load_user(user_id)
        sanitized_session = sanitize_session_id(session_id)
        ensure_checkout_access(checkout, user, sanitized_session)
        payments = payment_list_by_checkout(checkout)
        return [payment_summary(p) for p in payments]
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            f"Failed to list payments: {str(exc)}", 500, name="DATABASE_ERROR"
        )
