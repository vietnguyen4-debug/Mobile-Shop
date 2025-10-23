from typing import Any
from datetime import datetime, timezone
from ...core.exceptions import AppError

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