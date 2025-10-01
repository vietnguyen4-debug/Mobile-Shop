from mongoengine import *
from datetime import datetime,timezone, timedelta
from ..users.models import User

class TokenBlocklist(Document):
    users = ReferenceField(User)
    jti = StringField(required=True, unique=True)
    token_type = StringField(required=True, choices=("access", "refresh"))
    revoked = BooleanField(default=False)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    expires_at = DateTimeField(required=True)
    user = ReferenceField(User)

    meta = {
        "collection": "token_blocklist",
        "indexes": [
            {"fields": ["jti"], "unique": True},
            {"fields": ["expires_at"]},
        ]
    }

    @classmethod
    def revoke(cls,user, jti: str, token_type: str, ttl_seconds: int):
        return cls(
            user = user,
            jti = jti,
            token_type = token_type,
            revoked = True,
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        ).save()