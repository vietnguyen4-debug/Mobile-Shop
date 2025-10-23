from typing import Any, Optional
from datetime import datetime, timezone

from ..checkout.models import Checkout
from ..users.models import User
from ...core.exceptions import AppError
from ...core.utils import parse_oid

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


def _load_checkout(checkout_id: Any) -> Checkout:
    if checkout_id is None:
        raise AppError("Checkout identifier is required", 400, name="INVALID_CHECKOUT")
    oid = parse_oid(str(checkout_id))
    if not oid:
        raise AppError("Invalid checkout identifier", 400, name="INVALID_CHECKOUT")
    try:
        checkout = Checkout.objects(id=oid).first()
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to load checkout: {str(exc)}", 500, name="DATABASE_ERROR"
        )
    if not checkout:
        raise AppError("Checkout not found", 404, name="CHECKOUT_NOT_FOUND")
    return checkout


def _load_user(user_id: Optional[str]) -> Optional[User]:
    if not user_id:
        return None
    oid = parse_oid(str(user_id))
    if not oid:
        raise AppError("Invalid user identifier", 400, name="INVALID_USER")
    try:
        user = User.objects(id=oid).first()
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to load user: {str(exc)}", 500, name="DATABASE_ERROR"
        )
    if not user:
        raise AppError("User not found", 404, name="INVALID_USER")
    return user


def _sanitize_session_id(session_id: Any) -> Optional[str]:
    if session_id is None:
        return None
    if not isinstance(session_id, str):
        raise AppError("Session identifier must be a string", 400, name="INVALID_SESSION")
    trimmed = session_id.strip()
    if not trimmed:
        return None
    if len(trimmed) > 120:
        raise AppError("Session identifier too long", 400, name="INVALID_SESSION")
    return trimmed


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