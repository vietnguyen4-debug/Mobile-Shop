from ...core.validation import require_fields
from .mappers import shipment_public
from .repositories import *
from .service_helpers import (
    _normalize_note,
    _normalize_recipient_name,
    _normalize_recipient_phone,
    _resolve_address,
    _ensure_checkout_paid,
    _validate_shipment_status,
    _ensure_valid_shipment_transition,
)
from ...core.utils import *

def s_assign_shipment(user_id: Optional[str], payload: dict) -> dict:
    require_fields(payload, "checkout_id")
    try:
        checkout = load_checkout(payload.get("checkout_id"))
        user = load_user(user_id)
        session_id = sanitize_session_id(payload.get("session_id"))
        ensure_checkout_access(checkout, user, session_id)

        has_recipient_name = "recipient_name" in payload
        has_recipient_phone = "recipient_phone" in payload
        has_note = "note" in payload

        recipient_name = (
            _normalize_recipient_name(payload.get("recipient_name"))
            if has_recipient_name
            else None
        )
        recipient_phone = (
            _normalize_recipient_phone(payload.get("recipient_phone"))
            if has_recipient_phone
            else None
        )
        note = _normalize_note(payload.get("note")) if has_note else None

        shipment = shipment_get_by_checkout(checkout)
        if shipment:
            address_doc = getattr(shipment, "address", None)
            current_name = getattr(address_doc, "recipient_name", None) if address_doc else None
            current_phone = getattr(address_doc, "recipient_phone", None) if address_doc else None

            if not has_recipient_name and not current_name:
                raise AppError("Recipient name is required", 400, name="INVALID_RECIPIENT_NAME")
            if not has_recipient_phone and not current_phone:
                raise AppError("Recipient phone is required", 400, name="INVALID_RECIPIENT_PHONE")

            address = _resolve_address(
                user,
                None,
                payload.get("address"),
            )

            if address_doc:
                address_doc.user = user
                address_doc.session_id = session_id
                address_doc.source = address.source
                address_doc.address_line = address.address_line
                address_doc.city = address.city
                address_doc.user_address_id = address.user_address_id
                if has_recipient_name:
                    address_doc.recipient_name = recipient_name
                if has_recipient_phone:
                    address_doc.recipient_phone = recipient_phone
                if has_note:
                    address_doc.note = note
                address_doc = shipment_address_save(address_doc)
            else:
                # If shipment exists without address, enforce recipient info before creating
                if not recipient_name:
                    raise AppError("Recipient name is required", 400, name="INVALID_RECIPIENT_NAME")
                if not recipient_phone:
                    raise AppError("Recipient phone is required", 400, name="INVALID_RECIPIENT_PHONE")

                address = _resolve_address(
                    user,
                    None,
                    payload.get("address"),
                )

                address_doc = shipment_address_create(
                    {
                        "user": user,
                        "session_id": session_id,
                        "source": address.source,
                        "address_line": address.address_line,
                        "city": address.city,
                        "recipient_name": recipient_name,
                        "recipient_phone": recipient_phone,
                        "note": note,
                        "user_address_id": address.user_address_id,
                    }
                )
                shipment.address = address_doc

            shipment.user = user
            shipment.session_id = session_id
            shipment.source = address.source
            shipment.address = address_doc
            shipment = shipment_save(shipment)
        else:
            # New shipment requires recipient info if not supplied earlier
            if not (has_recipient_name and recipient_name):
                raise AppError("Recipient name is required", 400, name="INVALID_RECIPIENT_NAME")
            if not (has_recipient_phone and recipient_phone):
                raise AppError("Recipient phone is required", 400, name="INVALID_RECIPIENT_PHONE")

            address = _resolve_address(
                user,
                None,
                payload.get("address"),
            )

            address_doc = shipment_address_create(
                {
                    "user": user,
                    "session_id": session_id,
                    "source": address.source,
                    "address_line": address.address_line,
                    "city": address.city,
                    "recipient_name": recipient_name,
                    "recipient_phone": recipient_phone,
                    "note": note,
                    "user_address_id": address.user_address_id,
                }
            )
            shipment = shipment_create(
                {
                    "checkout": checkout,
                    "user": user,
                    "session_id": session_id,
                    "source": address.source,
                    "status": "pending",
                    "address": address_doc,
                }
            )
        return shipment_public(shipment)
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to save shipment: {str(exc)}", 500, name="DATABASE_ERROR"
        )


def s_get_shipment_for_checkout(
    user_id: Optional[str], checkout_id: str, session_id: Optional[str]
) -> dict:
    try:
        checkout = load_checkout(checkout_id)
        user = load_user(user_id)
        sanitized_session = sanitize_session_id(session_id)
        ensure_checkout_access(checkout, user, sanitized_session)
        shipment = shipment_get_by_checkout(checkout)
        if not shipment:
            raise AppError("Shipment not found", 404, name="SHIPMENT_NOT_FOUND")
        return shipment_public(shipment)
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to retrieve shipment: {str(exc)}", 500, name="DATABASE_ERROR"
        )

def s_admin_update_shipment_status(shipment_id: str, payload: dict) -> dict:
    """
    Admin-only shipment status update.
    Requires at least one completed payment for the shipment's checkout (except cancelling).
    """
    payload = payload or {}
    require_fields(payload, "status")
    try:
        shipment = shipment_get_by_id(shipment_id)
        if not shipment:
            raise AppError("Shipment not found", 404, name="SHIPMENT_NOT_FOUND")

        target = _validate_shipment_status(payload.get("status"))
        current = getattr(shipment, "status", None) or "pending"
        if target == current:
            return shipment_public(shipment)

        checkout = getattr(shipment, "checkout", None)
        if target != "cancelled" and checkout:
            _ensure_checkout_paid(checkout)
        elif target != "cancelled" and not checkout:
            raise AppError("Shipment checkout not found", 400, name="CHECKOUT_NOT_FOUND")

        _ensure_valid_shipment_transition(current, target)

        shipment.status = target
        shipment = shipment_save(shipment)
        return shipment_public(shipment)
    except AppError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to update shipment status: {str(exc)}", 500, name="DATABASE_ERROR"
        )
