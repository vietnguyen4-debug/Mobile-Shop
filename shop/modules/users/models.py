from datetime import datetime,timezone
from mongoengine import *
from ...core import mixins

class Address(EmbeddedDocument):
    address_line = StringField(required=True)
    city = StringField(required=True)
    is_default = BooleanField(default=False)

class User(Document, mixins.AuditMixin):
    username = StringField(required=True, unique=True)
    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)
    first_name = StringField(max_length=50)
    last_name = StringField(max_length=50)
    role = StringField(choices=("user", "admin"), default="user")
    phone = StringField(max_length=15)
    avatar = StringField()
    last_login_at = DateTimeField()
    addresses = ListField(EmbeddedDocumentField(Address))

    meta = {
        "collection": "users",
        "indexes": [
            {"fields": ["username"], "unique": True},
            {"fields": ["email"], "unique": True},
            {"fields": ["-created_at"]},
        ]
    }

    def mark_login(self):
        self.last_login_at = datetime.now(timezone.utc)
        self.save()