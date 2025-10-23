from ...core.exceptions import AppError


def shipment_public(shipment):
    try:
        if shipment is None:
            return None
        address = getattr(shipment, "address", None)
        return {
            "id": str(shipment.id),
            "checkout_id": str(shipment.checkout.id) if getattr(shipment, "checkout", None) else None,
            "user_id": str(shipment.user.id) if getattr(shipment, "user", None) else None,
            "session_id": getattr(shipment, "session_id", None),
            "source": getattr(shipment, "source", None)
            or (getattr(address, "source", None) if address else None),
            "status": getattr(shipment, "status", None),
            "address_line": getattr(address, "address_line", None) if address else None,
            "city": getattr(address, "city", None) if address else None,
            "recipient_name": getattr(address, "recipient_name", None) if address else None,
            "recipient_phone": getattr(address, "recipient_phone", None) if address else None,
            "note": getattr(address, "note", None) if address else None,
            "user_address_id": getattr(address, "user_address_id", None) if address else None,
            "created_at": shipment.created_at.isoformat() if getattr(shipment, "created_at", None) else None,
            "updated_at": shipment.updated_at.isoformat() if getattr(shipment, "updated_at", None) else None,
        }
    except Exception as exc:
        raise AppError(f"Failed to map shipment: {str(exc)}", 500, name="MAPPING_ERROR")