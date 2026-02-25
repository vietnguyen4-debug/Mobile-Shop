from typing import Optional

from bson import ObjectId
from mongoengine.errors import NotUniqueError

from .models import Shipment, ShipmentAddress


def shipment_get_by_checkout(checkout) -> Optional[Shipment]:
    # Return the active (non-cancelled) shipment for a checkout.
    return (
        Shipment.objects(checkout=checkout, status__ne="cancelled")
        .order_by("-created_at")
        .first()
    )


def shipment_list_by_checkout(checkout) -> list[Shipment]:
    return list(Shipment.objects(checkout=checkout).order_by("-created_at"))


def shipment_get_by_id(shipment_id) -> Optional[Shipment]:
    try:
        oid = ObjectId(str(shipment_id))
    except Exception:
        return None
    return Shipment.objects(id=oid).first()


def shipment_create(data: dict) -> Shipment:
    shipment = Shipment(**data)
    try:
        shipment.save()
        return shipment
    except NotUniqueError:
        # Another non-cancelled shipment already exists for this checkout.
        checkout = data.get("checkout")
        existing = shipment_get_by_checkout(checkout)
        if existing:
            return existing
        raise


def shipment_save(shipment: Shipment) -> Shipment:
    shipment.save()
    return shipment


def shipment_address_create(data: dict) -> ShipmentAddress:
    address = ShipmentAddress(**data)
    address.save()
    return address


def shipment_address_save(address: ShipmentAddress) -> ShipmentAddress:
    address.save()
    return address
