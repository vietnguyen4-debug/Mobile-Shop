from typing import Optional

from bson import ObjectId

from .models import Shipment, ShipmentAddress


def shipment_get_by_checkout(checkout) -> Optional[Shipment]:
    return Shipment.objects(checkout=checkout).first()


def shipment_get_by_id(shipment_id) -> Optional[Shipment]:
    try:
        oid = ObjectId(str(shipment_id))
    except Exception:
        return None
    return Shipment.objects(id=oid).first()


def shipment_create(data: dict) -> Shipment:
    shipment = Shipment(**data)
    shipment.save()
    return shipment


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