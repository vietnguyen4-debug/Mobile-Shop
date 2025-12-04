from mongoengine import *

from ...core.mixins import AuditMixin

class Checkout(Document, AuditMixin):
    cart = ReferenceField("Cart", required=True, unique=True)
    user = ReferenceField("User", required=False, null=True)
    session_id = StringField(required=False, max_length=120)
    status = StringField(
        default="pending",
        choices=("pending", "processing", "completed", "cancelled"),
    )
    currency = StringField(default="VND", max_length=10)
    total_amount = FloatField(default=0.0, min_value=0)
    expires_at = DateTimeField(required=False, null=True)

    meta = {
        "collection": "checkout",
        "indexes": [
            {"fields": ["cart"], "unique": True, "name": "idx_checkout_cart"},
            {"fields": ["user", "-created_at"], "name": "idx_checkout_user_created"},
            {"fields": ["session_id"], "name": "idx_checkout_session"},
            {"fields": ["status", "-created_at"], "name": "idx_checkout_status_created"},
            {"fields": ["expires_at"], "name": "idx_checkout_expires_at"},
        ],
    }

    def clean(self):
        if not self.user and not (self.session_id and self.session_id.strip()):
            raise ValueError("Either user or session_id must be provided for checkout.")
