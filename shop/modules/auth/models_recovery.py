from mongoengine import *
from datetime import datetime,timezone
from ..users.models import User

class PasswordReset(Document):
    user       = ReferenceField(User, required=True)
    token      = StringField(required=True, unique=True)   # random uuid
    expires_at = DateTimeField(required=True)
    used       = BooleanField(default=False)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    meta       = {"collection": "password_reset", "indexes": ["token", "expires_at"]}

class EmailVerification(Document):
    user        = ReferenceField(User, required=True)
    token       = StringField(required=True, unique=True)
    expires_at  = DateTimeField(required=True)
    verified_at = DateTimeField()
    new_email = EmailField()
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    meta        = {"collection": "email_verification", "indexes": ["token", "expires_at"]}