from datetime import datetime, timezone
from mongoengine import DateTimeField, BooleanField

class AuditMixin:
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    is_active  = BooleanField(default=True)

    def save(self):
        self.updated_at = datetime.now(timezone.utc)
