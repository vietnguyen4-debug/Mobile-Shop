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
        # Match existing indexes in DB (background: false) to avoid option mismatch
        "index_background": False,
        "indexes": [
            {
                "fields": ["checkout", "method"],
                # Allow multiple payments per checkout/method (non-unique)
                "name": "idx_payment_checkout_method",
            },
            {"fields": ["status", "-created_at"], "name": "idx_payment_status_created"},
        ],
    }
