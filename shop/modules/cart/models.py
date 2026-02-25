from datetime import datetime, timezone

from bson import ObjectId
from mongoengine import (
    Document,
    EmbeddedDocument,
    EmbeddedDocumentListField,
    ObjectIdField,
    ReferenceField,
    StringField,
    IntField,
    DateTimeField,
    ValidationError,
)

from ...core.mixins import AuditMixin


class CartItem(EmbeddedDocument, AuditMixin):
    id = ObjectIdField(default=ObjectId)
    product: ReferenceField = ReferenceField("Product", required=True)
    quantity: IntField = IntField(default=1, min_value=1, required=True)


class Cart(Document, AuditMixin):
    user = ReferenceField("User", required=False, null=True)
    session_id = StringField(required=False, max_length=120)
    status = StringField(
        default="active",
        choices=("active", "merged", "converted"),
    )
    guest_expires_at = DateTimeField(required=False, null=True)
    items = EmbeddedDocumentListField(CartItem, default=list)

    meta = {
        "collection": "cart",
        "indexes": [
            {"fields": ["user", "session_id"]},
            {"fields": ["status"]},
            {"fields": ["-created_at"]},
            {"fields": ["guest_expires_at"]},
        ]
    }

    def clean(self):
        if not self.user and not(self.session_id and self.session_id.strip()):
            raise ValidationError("Either user or session_id must be provided.")

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now(timezone.utc)
        return super().save(*args, **kwargs)
