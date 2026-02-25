from typing import Optional
import os
import logging

from .service_helpers import (
    _parse_amount,
    _normalize_currency,
    _build_vnpay_payment_url,
    _vnpay_hash,
    vnpay_querydr,
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
from ..shipment.repositories import shipment_create, shipment_get_by_checkout
from datetime import datetime, timezone
from datetime import timedelta
from ...core.celery_client import enqueue_task


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


def _is_guest_user(user) -> bool:
    if not user:
        return False
    username = getattr(user, "username", "") or ""
    email = getattr(user, "email", "") or ""
    return username.startswith("guest_") and email.endswith("@guest.local")


def _ensure_pending_shipment_for_checkout(checkout) -> None:
    """
    Ensure a Shipment exists for the checkout, defaulting to status=pending.
    Used when payment completes so shipping can be managed by admin.
    """
    if not checkout:
        return
    if shipment_get_by_checkout(checkout):
        return

    user = getattr(checkout, "user", None)
    session_id = getattr(checkout, "session_id", None)
    source = "guest" if (session_id or _is_guest_user(user)) else "user"
    try:
        shipment_create(
            {
                "checkout": checkout,
                "user": user,
                "session_id": session_id,
                "source": source,
                "status": "pending",
                "address": None,
            }
        )
    except Exception:
        # Duplicate key/race: another worker created it.
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
    provider_value = str(provider).strip().lower() if provider is not None else "vnpay"
    if provider_value != "vnpay":
        raise AppError("Unsupported online payment provider", 400, name="UNSUPPORTED_PROVIDER")
    note = payload.get("note")
    ip_addr = payload.get("ip_addr")

    data = {
        "checkout_id": str(checkout.id),
        "session_id": session_id,
        "provider": provider_value,
        "note": note,
        "_amount_override": outstanding,
    }
    # Use checkout currency when forcing amount.
    data["currency"] = getattr(checkout, "currency", "VND")

    payment = _create_payment(user_id, data, method="online", require_access=False)
    built = _build_vnpay_payment_url(payment, ip_addr=str(ip_addr) if ip_addr else None)
    if built:
        payment_url, create_date = built
        payment["payment_url"] = payment_url
        # Persist vnp_CreateDate so QueryDR can use the exact transaction date.
        try:
            payment_doc = payment_get_by_id(payment.get("id"))
            if payment_doc:
                payment_doc.provider_create_date = create_date
                payment_save(payment_doc)
        except Exception:
            pass
    return payment


def s_inspect_vnpay_return(params: Optional[dict]) -> dict:
    """
    Inspect VNPAY return params for UI/debugging without mutating payment state.
    """
    params = dict(params or {})
    txn_ref = str(params.get("vnp_TxnRef") or "")
    rsp_code = str(params.get("vnp_ResponseCode") or "")
    txn_status = str(params.get("vnp_TransactionStatus") or "")

    signature_valid = None
    secret = os.environ.get("VNPAY_SECRET_KEY", "")
    received_hash = (params.get("vnp_SecureHash") or "").upper()
    if secret and received_hash:
        try:
            signature_valid = received_hash == _vnpay_hash(params, secret)
        except Exception:
            signature_valid = False

    payment = payment_get_by_provider_ref(txn_ref) if txn_ref else None
    checkout = getattr(payment, "checkout", None) if payment else None

    return {
        "txn_ref": txn_ref,
        "response_code": rsp_code,
        "transaction_status": txn_status,
        "signature_valid": signature_valid,
        "payment_id": str(getattr(payment, "id", "")) if payment else "",
        "checkout_id": str(getattr(checkout, "id", "")) if checkout else "",
        "payment_status": str(getattr(payment, "status", "")) if payment else "",
    }


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

    # Basic required params: prevent accidentally treating a "pay" URL as an IPN/Return callback.
    txn_ref = params.get("vnp_TxnRef")
    amount_param = params.get("vnp_Amount")
    rsp_code = params.get("vnp_ResponseCode")
    missing = [k for k, v in (("vnp_TxnRef", txn_ref), ("vnp_Amount", amount_param), ("vnp_ResponseCode", rsp_code)) if not v]
    if missing:
        _vnp_logger.warning(
            "VNPAY webhook missing required params",
            extra={"missing": missing, "txn_ref": txn_ref},
        )
        return ({"RspCode": "99", "Message": "Missing required params"}, 200)

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

    pay_date = params.get("vnp_PayDate")
    txn_no = params.get("vnp_TransactionNo")
    txn_status = params.get("vnp_TransactionStatus")
    bank_code = params.get("vnp_BankCode")
    bank_tran_no = params.get("vnp_BankTranNo")
    card_type = params.get("vnp_CardType")

    payment = payment_get_by_provider_ref(txn_ref)
    if not payment:
        _vnp_logger.warning(
            "VNPAY webhook payment not found",
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

    is_success = (rsp_code == "00") and (txn_status in (None, "", "00"))

    # Only mark payment completed when VNPAY reports success.
    if not is_success:
        if getattr(payment, "status", None) == "completed":
            _vnp_logger.info(
                "VNPAY webhook already completed payment received non-success callback",
                extra={"txn_ref": txn_ref, "rsp_code": rsp_code, "txn_status": txn_status},
            )
            return ({"RspCode": "02", "Message": "Order already confirmed"}, 200)
        if getattr(payment, "status", None) != "completed":
            try:
                payment.provider_rsp_code = rsp_code
                if txn_no:
                    payment.provider_txn_no = str(txn_no)
                if bank_code:
                    payment.provider_bank_code = str(bank_code)
                if bank_tran_no:
                    payment.provider_bank_tran_no = str(bank_tran_no)
                if card_type:
                    payment.provider_card_type = str(card_type)
                if pay_date:
                    payment.provider_pay_date = str(pay_date)
                if getattr(payment, "status", None) != "cancelled":
                    payment.status = "cancelled"
                payment_save(payment)
            except Exception:
                _vnp_logger.exception(
                    "VNPAY webhook failed to mark payment cancelled",
                    extra={"txn_ref": txn_ref, "rsp_code": rsp_code},
                )
        _vnp_logger.info(
            "VNPAY webhook non-success response",
            extra={"txn_ref": txn_ref, "rsp_code": rsp_code, "txn_status": txn_status},
        )
        # Acknowledge IPN receipt after persisting failure/cancel state.
        return ({"RspCode": "00", "Message": "OK"}, 200)

    if payment.status == "completed":
        _vnp_logger.info(
            "VNPAY webhook duplicate success callback",
            extra={"txn_ref": txn_ref, "rsp_code": rsp_code, "txn_status": txn_status},
        )
        return ({"RspCode": "02", "Message": "Order already confirmed"}, 200)

    if getattr(payment, "status", None) == "cancelled":
        _vnp_logger.warning(
            "VNPAY webhook success received for locally cancelled payment; recovering to completed",
            extra={"txn_ref": txn_ref},
        )

    if payment.status != "completed":
        payment.status = "completed"
        payment.provider_rsp_code = rsp_code or "00"
        if txn_no:
            payment.provider_txn_no = str(txn_no)
        if bank_code:
            payment.provider_bank_code = str(bank_code)
        if bank_tran_no:
            payment.provider_bank_tran_no = str(bank_tran_no)
        if card_type:
            payment.provider_card_type = str(card_type)
        if pay_date:
            payment.provider_pay_date = str(pay_date)
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

        try:
            _ensure_pending_shipment_for_checkout(getattr(payment, "checkout", None))
        except Exception:
            _vnp_logger.exception(
                "VNPAY webhook failed to ensure pending shipment",
                extra={"txn_ref": txn_ref, "payment_id": str(getattr(payment, "id", ""))},
            )

        _cancel_other_pending_payments(payment)
        _vnp_logger.info(
            "VNPAY payment marked completed",
            extra={
                "payment_id": str(getattr(payment, "id", "")),
                "txn_ref": txn_ref,
                "amount": amount,
                "rsp_code": rsp_code,
                "txn_status": txn_status,
                "pay_date": pay_date,
            },
        )
        try:
            enqueue_task("tasks.on_payment_completed", args=[str(getattr(payment, "id", ""))])
        except Exception:
            pass

    # Respond using merchant IPN acknowledgement codes, not provider response codes.
    rsp_code = "00"
    message = "OK"
    _vnp_logger.info(
        "VNPAY webhook response",
        extra={"RspCode": rsp_code, "Message": message, "txn_ref": txn_ref},
    )
    return ({"RspCode": rsp_code, "Message": message}, 200)


def _vnpay_transaction_date_from_payment(payment) -> str:
    created_at = getattr(payment, "created_at", None)
    if not isinstance(created_at, datetime):
        created_at = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    tz = timezone(timedelta(hours=7))
    return created_at.astimezone(tz).strftime("%Y%m%d%H%M%S")


def s_admin_query_vnpay(payment_id: str, payload: Optional[dict] = None) -> dict:
    """
    Admin helper to query VNPAY for a transaction result (QueryDR) and
    optionally update local payment status/metadata.
    """
    payload = payload or {}
    payment = payment_get_by_id(payment_id)
    if not payment:
        raise AppError("Payment not found", 404, name="PAYMENT_NOT_FOUND")
    if getattr(payment, "provider", None) != "vnpay":
        raise AppError("Payment provider is not VNPAY", 400, name="INVALID_PROVIDER")

    txn_ref = getattr(payment, "provider_ref", None) or str(getattr(payment, "id", ""))
    transaction_date = payload.get("transaction_date") or getattr(payment, "provider_create_date", None) or _vnpay_transaction_date_from_payment(payment)
    order_info = payload.get("order_info") or f"Query payment {str(getattr(payment, 'id', ''))}"
    ip_addr = payload.get("ip_addr") or "127.0.0.1"

    resp = vnpay_querydr(
        txn_ref=str(txn_ref),
        transaction_date=str(transaction_date),
        order_info=str(order_info),
        ip_addr=str(ip_addr),
    )

    # Persist some provider metadata for debugging/audit.
    payment.provider_rsp_code = resp.get("vnp_ResponseCode") or getattr(payment, "provider_rsp_code", None)
    payment.provider_txn_no = resp.get("vnp_TransactionNo") or getattr(payment, "provider_txn_no", None)
    payment.provider_bank_code = resp.get("vnp_BankCode") or getattr(payment, "provider_bank_code", None)
    payment.provider_bank_tran_no = resp.get("vnp_BankTranNo") or getattr(payment, "provider_bank_tran_no", None)
    payment.provider_card_type = resp.get("vnp_CardType") or getattr(payment, "provider_card_type", None)
    payment.provider_pay_date = resp.get("vnp_PayDate") or getattr(payment, "provider_pay_date", None)

    rsp_code = resp.get("vnp_ResponseCode")
    txn_status = resp.get("vnp_TransactionStatus")
    pay_date = resp.get("vnp_PayDate")

    # Update local status if VNPAY confirms success.
    if rsp_code == "00" and (txn_status in (None, "", "00")):
        if getattr(payment, "status", None) != "completed":
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
            payment_save(payment)
            try:
                _ensure_pending_shipment_for_checkout(getattr(payment, "checkout", None))
            except Exception:
                _vnp_logger.exception(
                    "VNPAY QueryDR failed to ensure pending shipment",
                    extra={"txn_ref": txn_ref, "payment_id": str(getattr(payment, "id", ""))},
                )
            _cancel_other_pending_payments(payment)
            try:
                enqueue_task("tasks.on_payment_completed", args=[str(getattr(payment, "id", ""))])
            except Exception:
                pass
    else:
        payment_save(payment)

    return {
        "payment": payment_public(payment),
        "vnpay": resp,
    }


def s_reconcile_pending_vnpay_payments(
    *,
    limit: int = 100,
    min_age_seconds: int = 300,
) -> dict:
    """
    Best-effort reconciliation for pending VNPAY payments using QueryDR.
    Useful when IPN/return was missed.
    """
    now = datetime.now(timezone.utc)
    before = now - timedelta(seconds=int(min_age_seconds))
    pending = payment_list_pending_vnpay(before=before, limit=int(limit))

    checked = 0
    completed = 0
    errors = 0

    for p in pending:
        checked += 1
        try:
            result = s_admin_query_vnpay(str(getattr(p, "id", "")), {})
            if (result.get("payment") or {}).get("status") == "completed":
                completed += 1
        except Exception:
            errors += 1
            _vnp_logger.exception(
                "VNPAY reconcile failed",
                extra={"payment_id": str(getattr(p, "id", "")), "txn_ref": getattr(p, "provider_ref", None)},
            )

    return {"checked": checked, "completed": completed, "errors": errors}


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
