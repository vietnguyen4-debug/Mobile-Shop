from mongoengine import Document, ReferenceField, StringField

from ...core.mixins import AuditMixin


class ShipmentAddress(Document, AuditMixin):
    user = ReferenceField("User", required=False, null=True)
    session_id = StringField(required=False, max_length=120)
    source = StringField(required=True, choices=("user", "guest"))
    address_line = StringField(required=True, max_length=255)
    city = StringField(required=True, max_length=120)
    recipient_name = StringField(required=False, max_length=120)
    recipient_phone = StringField(required=False, max_length=30)
    note = StringField(required=False, max_length=500)
    user_address_id = StringField(required=False, max_length=64)

    meta = {
        "collection": "shipment_address",
        "indexes": [
            {"fields": ["user", "-created_at"], "name": "idx_shipment_address_user_created"},
            {"fields": ["session_id"], "name": "idx_shipment_address_session"},
            {"fields": ["source", "-created_at"], "name": "idx_shipment_address_source_created"},
        ],
    }


class Shipment(Document, AuditMixin):
    checkout = ReferenceField("Checkout", required=True)
    user = ReferenceField("User", required=False, null=True)
    address = ReferenceField("ShipmentAddress", required=False, null=True)
    session_id = StringField(required=False, max_length=120)
    source = StringField(required=True, choices=("user", "guest"))
    status = StringField(
        default="pending",
        choices=("pending", "processing", "shipped", "delivered", "cancelled"),
    )

    meta = {
        "collection": "shipment",
        "indexes": [
            {"fields": ["checkout"], "name": "idx_shipment_checkout"},
            # Enforce at most one non-cancelled shipment per checkout,
            # while allowing multiple cancelled shipments as history.
            {
                "fields": ["checkout"],
                "unique": True,
                "name": "idx_shipment_checkout_active_unique",
                "partialFilterExpression": {"status": {"$ne": "cancelled"}},
            },
            {"fields": ["status", "-created_at"], "name": "idx_shipment_status_created"},
        ],
    }
