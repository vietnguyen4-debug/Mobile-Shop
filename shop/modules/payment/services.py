from service_helpers import *
from .service_helpers import _load_checkout, _parse_amount, _normalize_currency, _load_user, _sanitize_session_id, \
    _parse_paid_at
from ...core.validation import require_fields
from .repositories import *
from .mappers import payment_public

def s_create_offline_payment(user_id: str | None, payload: dict) -> dict:
    require_fields(payload, "checkout_id", "amount")
    try:
        checkout = _load_checkout(payload.get("checkout_id"))
        user = _load_user(user_id)
        amount = _parse_amount(payload.get("amount"))
        currency = _normalize_currency(payload.get("currency"))
        note = payload.get("note")
        if note is not None and not isinstance(note, str):
            raise AppError("Note must be a string", 400, name="INVALID_NOTE")
        cleaned_note = note.strip() if isinstance(note, str) else None
        session_id = _sanitize_session_id(payload.get("session_id"))

        payment = payment_create(
            {
                "checkout": checkout,
                "user": user,
                "session_id": session_id,
                "method": "offline",
                "amount": amount,
                "currency": currency,
                "status": "pending",
                "note": cleaned_note,
            }
        )
        return payment_public(payment)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            f"Failed to create offline payment: {str(exc)}",
            500,
            name="DATABASE_ERROR",
        )


def s_complete_offline_payment(payment_id: str, payload: Optional[dict]) -> dict:
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
        payment = payment_save(payment)
        return payment_public(payment)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Failed to complete payment: {str(exc)}", 500, name="DATABASE_ERROR")


def s_get_payment(payment_id: str) -> dict:
    try:
        payment = payment_get_by_id(payment_id)
        if not payment:
            raise AppError("Payment not found", 404, name="PAYMENT_NOT_FOUND")
        return payment_public(payment)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Failed to retrieve payment: {str(exc)}", 500, name="DATABASE_ERROR")


def s_list_payments_by_checkout(checkout_id: str) -> list[dict]:
    try:
        checkout = _load_checkout(checkout_id)
        payments = payment_list_by_checkout(checkout)
        return [payment_public(p) for p in payments]
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            f"Failed to list payments: {str(exc)}", 500, name="DATABASE_ERROR"
        )
