import hashlib
import hmac
import os
import urllib.parse
from typing import Any
from datetime import datetime, timezone, timedelta
from ...core.exceptions import AppError
import logging


_vnp_logger = logging.getLogger("shop.payment.vnpay")

def _parse_amount(value: Any) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise AppError("Invalid amount: expected a numeric value", 400, name="INVALID_AMOUNT")
    if amount <= 0:
        raise AppError("Amount must be greater than zero", 400, name="INVALID_AMOUNT")
    return amount


def _normalize_currency(value: Any) -> str:
    if value is None:
        return "VND"
    if not isinstance(value, str):
        raise AppError("Currency must be a string", 400, name="INVALID_CURRENCY")
    currency = value.strip().upper()
    if not currency:
        return "VND"
    if len(currency) > 10:
        raise AppError("Currency is too long", 400, name="INVALID_CURRENCY")
    return currency

def _parse_paid_at(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return datetime.now(timezone.utc)
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            raise AppError("paid_at must be an ISO formatted datetime", 400, name="INVALID_PAID_AT")
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise AppError("paid_at must be an ISO formatted datetime", 400, name="INVALID_PAID_AT")


def _vnpay_hash(params: dict, secret: str) -> str:
    items = [
        (k, v)
        for k, v in params.items()
        if k not in ("vnp_SecureHash", "vnp_SecureHashType")
    ]
    items.sort(key=lambda kv: kv[0])
    raw = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in items)
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha512).hexdigest().upper()


def _build_vnpay_payment_url(payment: dict) -> str | None:
    """
    Build a VNPAY payment URL from payment data; returns None if not applicable.
    """
    if not isinstance(payment, dict):
        return None
    if payment.get("provider") != "vnpay":
        return None

    tmn_code = os.environ.get("VNPAY_TMN_CODE")
    secret = os.environ.get("VNPAY_SECRET_KEY")
    return_url = os.environ.get("VNPAY_RETURN_URL")
    ipn_url = os.environ.get("VNPAY_IPN_URL")
    payment_url = os.environ.get(
        "VNPAY_PAYMENT_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    )
    if not all([tmn_code, secret, return_url, ipn_url, payment_url]):
        _vnp_logger.warning(
            "VNPAY config missing; skipping URL build",
            extra={
                "tmn_code": bool(tmn_code),
                "has_secret": bool(secret),
                "has_return_url": bool(return_url),
                "has_ipn_url": bool(ipn_url),
                "payment_url": bool(payment_url),
            },
        )
        return None

    provider_ref = payment.get("provider_ref") or payment.get("id")
    amount = payment.get("amount")
    checkout_id = payment.get("checkout_id")
    if provider_ref is None or amount is None:
        _vnp_logger.warning(
            "VNPAY build URL missing provider_ref/amount",
            extra={"provider_ref": provider_ref, "amount": amount},
        )
        return None
    try:
        amount_int = int(round(float(amount) * 100))
    except Exception:
        _vnp_logger.exception(
            "VNPAY build URL failed to parse amount",
            extra={"raw_amount": amount},
        )
        return None

    tz = timezone(timedelta(hours=7))
    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": tmn_code,
        "vnp_Amount": amount_int,
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": provider_ref,
        "vnp_OrderInfo": f"Thanh toan checkout {checkout_id}" if checkout_id else "Thanh toan don hang",
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": return_url,
        "vnp_IpnUrl": ipn_url,
        "vnp_CreateDate": datetime.now(tz).strftime("%Y%m%d%H%M%S"),
    }
    params["vnp_SecureHashType"] = "HMACSHA512"
    params["vnp_SecureHash"] = _vnpay_hash(params, secret)

    # Debug log the outgoing VNPAY URL (without exposing secret).
    try:
        _vnp_logger.info(
            "VNPAY payment URL built",
            extra={
                "provider_ref": provider_ref,
                "amount": amount_int,
                "checkout_id": checkout_id,
                "create_date": params.get("vnp_CreateDate"),
                "payment_url": payment_url,
            },
        )
    except Exception:
        # Logging must not break payment flow.
        pass
    query = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in params.items())
    return f"{payment_url}?{query}"
