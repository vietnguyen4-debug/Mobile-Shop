from mongoengine import Document, ReferenceField, StringField

from ...core.mixins import AuditMixin


class Checkout(Document, AuditMixin):
    user = ReferenceField("User", required=False, null=True)
    session_id = StringField(required=False, max_length=120)
    status = StringField(
        default="pending",
        choices=("pending", "processing", "completed", "cancelled"),
    )

    meta = {
        "collection": "checkout",
        "indexes": [
            {"fields": ["user", "-created_at"], "name": "idx_checkout_user_created"},
            {"fields": ["session_id"], "name": "idx_checkout_session"},
            {"fields": ["status", "-created_at"], "name": "idx_checkout_status_created"},
        ],
    }