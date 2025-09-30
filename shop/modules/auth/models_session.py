from mongoengine import *
from datetime import datetime,timezone
from ..users.models import User

class DeviceSession(Document):
    user = ReferenceField(User)
    device_name = StringField(required=True)
    user_agent = StringField(required=True)
    ip_address = StringField(required=True)
    refresh_jti = StringField(required=True)
    last_seen_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    is_revoked = BooleanField(default=False)
    meta = {
        "collection": "device_sessions",
        "indexes": [
            {"fields": ["user"]},
            {"fields": ["refresh_jti"]},
            {"fields": ["-last_seen_at"]},
        ]
    }