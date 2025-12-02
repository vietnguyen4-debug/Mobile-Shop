from ...core.exceptions import AppError


def payment_summary(payment):
    try:
        if payment is None:
            return None
        return {
            "id": str(payment.id),
            "checkout_id": str(payment.checkout.id) if getattr(payment, "checkout", None) else None,
            "method": getattr(payment, "method", None),
            "amount": getattr(payment, "amount", None),
            "currency": getattr(payment, "currency", None),
            "status": getattr(payment, "status", None),
            "paid_at": payment.paid_at.isoformat() if getattr(payment, "paid_at", None) else None,
        }
    except Exception as exc:
        raise AppError(f"Failed to map payment summary: {str(exc)}", 500, name="MAPPING_ERROR")


def payment_public(payment):
    try:
        if payment is None:
            return None
        return {
            "id": str(payment.id),
            "checkout_id": str(payment.checkout.id) if getattr(payment, "checkout", None) else None,
            "user_id": str(payment.user.id) if getattr(payment, "user", None) else None,
            "session_id": getattr(payment, "session_id", None),
            "method": getattr(payment, "method", None),
            "amount": getattr(payment, "amount", None),
            "currency": getattr(payment, "currency", None),
            "status": getattr(payment, "status", None),
            "note": getattr(payment, "note", None),
            "paid_at": payment.paid_at.isoformat() if getattr(payment, "paid_at", None) else None,
            "created_at": payment.created_at.isoformat() if getattr(payment, "created_at", None) else None,
            "updated_at": payment.updated_at.isoformat() if getattr(payment, "updated_at", None) else None,
        }
    except Exception as exc:
        raise AppError(f"Failed to map payment: {str(exc)}", 500, name="MAPPING_ERROR")
