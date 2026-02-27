import hashlib
import hmac
import os
import urllib.parse
from typing import Any
from datetime import datetime, timezone, timedelta
from ...core.exceptions import AppError
import logging
from uuid import uuid4
import httpx


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

def _now_vn_str() -> str:
    tz = timezone(timedelta(hours=7))
    return datetime.now(tz).strftime("%Y%m%d%H%M%S")

def _vnpay_api_hash_pipe(values: list[str], secret: str) -> str:
    raw = "|".join(values)
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha512).hexdigest().upper()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def is_vnpay_success(rsp_code: str | None, txn_status: str | None) -> bool:
    return (rsp_code == "00") and (txn_status in (None, "", "00"))


def payment_created_at_utc(payment: Any) -> datetime:
    created_at = getattr(payment, "created_at", None)
    if not isinstance(created_at, datetime):
        created_at = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at.astimezone(timezone.utc)


def vnpay_pending_timeout_seconds() -> int:
    expire_minutes = _env_int("VNPAY_EXPIRE_MINUTES", 15)
    grace_seconds = _env_int("VNPAY_PENDING_GRACE_SECONDS", 120)
    return max(60, (int(expire_minutes) * 60) + int(grace_seconds))


def vnpay_on_demand_querydr_min_age_seconds() -> int:
    return max(0, _env_int("VNPAY_ON_DEMAND_QUERYDR_MIN_AGE_SECONDS", 30))


def vnpay_querydr(
    *,
    txn_ref: str,
    transaction_date: str,
    order_info: str,
    ip_addr: str,
) -> dict:
    """
    Call VNPAY QueryDR API to query transaction result.
    Returns parsed JSON response (dict). Raises AppError on request failures.
    """
    tmn_code = os.environ.get("VNPAY_TMN_CODE", "")
    secret = os.environ.get("VNPAY_SECRET_KEY", "")
    api_url = os.environ.get(
        "VNPAY_QUERYDR_URL",
        "https://sandbox.vnpayment.vn/merchant_webapi/api/transaction",
    )
    if not tmn_code or not secret:
        raise AppError("VNPAY config missing", 500, name="VNPAY_NOT_CONFIGURED")

    request_id = uuid4().hex
    version = "2.1.0"
    command = "querydr"
    create_date = _now_vn_str()
    payload = {
        "vnp_RequestId": request_id,
        "vnp_Version": version,
        "vnp_Command": command,
        "vnp_TmnCode": tmn_code,
        "vnp_TxnRef": str(txn_ref),
        "vnp_OrderInfo": str(order_info or ""),
        "vnp_TransactionDate": str(transaction_date),
        "vnp_CreateDate": create_date,
        "vnp_IpAddr": str(ip_addr or "127.0.0.1"),
    }
    hash_values = [
        payload["vnp_RequestId"],
        payload["vnp_Version"],
        payload["vnp_Command"],
        payload["vnp_TmnCode"],
        payload["vnp_TxnRef"],
        payload["vnp_TransactionDate"],
        payload["vnp_CreateDate"],
        payload["vnp_IpAddr"],
        payload["vnp_OrderInfo"],
    ]
    payload["vnp_SecureHash"] = _vnpay_api_hash_pipe(hash_values, secret)

    _vnp_logger.info(
        "VNPAY QueryDR request",
        extra={
            "api_url": api_url,
            "txn_ref": txn_ref,
            "transaction_date": transaction_date,
            "request_id": request_id,
        },
    )

    try:
        resp = httpx.post(api_url, json=payload, timeout=15.0)
    except Exception as exc:
        raise AppError(f"VNPAY QueryDR request failed: {exc}", 502, name="VNPAY_QUERYDR_FAILED")

    try:
        data = resp.json()
    except Exception:
        raise AppError(
            f"VNPAY QueryDR invalid JSON response (HTTP {resp.status_code})",
            502,
            name="VNPAY_QUERYDR_INVALID_RESPONSE",
        )

    _vnp_logger.info(
        "VNPAY QueryDR response",
        extra={
            "http_status": resp.status_code,
            "txn_ref": txn_ref,
            "vnp_ResponseCode": data.get("vnp_ResponseCode"),
            "vnp_TransactionStatus": data.get("vnp_TransactionStatus"),
        },
    )
    return data


def _build_vnpay_payment_url(payment: dict, *, ip_addr: str | None = None) -> tuple[str, str] | None:
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
    payment_url = os.environ.get(
        "VNPAY_PAYMENT_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    )
    if not all([tmn_code, secret, return_url, payment_url]):
        _vnp_logger.warning(
            "VNPAY config missing; skipping URL build",
            extra={
                "tmn_code": bool(tmn_code),
                "has_secret": bool(secret),
                "has_return_url": bool(return_url),
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
    now = datetime.now(tz)
    create_date = now.strftime("%Y%m%d%H%M%S")
    expire_minutes = int(os.environ.get("VNPAY_EXPIRE_MINUTES", "15") or "15")
    expire_date = (now + timedelta(minutes=expire_minutes)).strftime("%Y%m%d%H%M%S")
    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": tmn_code,
        "vnp_Amount": amount_int,
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": provider_ref,
        "vnp_OrderInfo": f"Thanh toan checkout {checkout_id}" if checkout_id else "Thanh toan don hang",
        "vnp_OrderType": "other",
        "vnp_IpAddr": (ip_addr or "127.0.0.1")[:45],
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": return_url,
        "vnp_CreateDate": create_date,
        "vnp_ExpireDate": expire_date,
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
    query = "&".join(
        f"{k}={urllib.parse.quote_plus(str(params[k]))}" for k in sorted(params.keys())
    )
    return f"{payment_url}?{query}", create_date
