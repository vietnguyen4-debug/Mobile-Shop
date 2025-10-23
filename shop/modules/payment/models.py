from mongoengine import *

from ...core.mixins import AuditMixin


class Payment(Document, AuditMixin):
    checkout = ReferenceField("Checkout", required=True)
    user = ReferenceField("User", required=False, null=True)
    session_id = StringField(required=False, max_length=120)
    method = StringField(required=True, default="offline", choices=("offline",))
    amount = FloatField(required=True, min_value=0)
    currency = StringField(default="VND", max_length=10)
    status = StringField(
        default="pending",
        choices=("pending", "completed", "cancelled"),
    )
    note = StringField()
    paid_at = DateTimeField()

    meta = {
        "collection": "payment",
        "indexes": [
            {"fields": ["checkout", "method"], "name": "idx_payment_checkout_method"},
            {"fields": ["status", "-created_at"], "name": "idx_payment_status_created"},
        ],
    }