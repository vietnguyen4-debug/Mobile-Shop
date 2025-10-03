from datetime import datetime, timezone, timedelta
from typing import Optional
from .models_token import TokenBlocklist
from .models_session import DeviceSession
from .models_recovery import PasswordReset, EmailVerification
from ..users.models import User

def block_access(user: User, jti: str, ttl_seconds: int) -> TokenBlocklist:
    return TokenBlocklist.revoke(user, jti, "access", ttl_seconds)

def block_refresh(user: User, jti: str, ttl_seconds: int) -> TokenBlocklist:
    return TokenBlocklist.revoke(user, jti, "refresh", ttl_seconds)

def _is_revoked(jti: str) -> bool:
    return TokenBlocklist.objects(jti=jti, revoked=True).first() is not None

def list_sessions(user: User) ->list[DeviceSession]:
    return list(DeviceSession.objects(user=user).order_by("-last_seen_at"))

def revoke_sessions(user: User, session_id: str) -> bool:
    s = DeviceSession.objects(user=user, id=session_id).first()
    if not s: return False
    s.is_revoked = True
    if s.refresh_jti:
        block_refresh(user, s.refresh_jti, 7*24*3600)
    s.save()
    return True

def revoke_all_sessions(user: User) -> bool:
    for s in DeviceSession.objects(user=user, is_revoked=False):
        s.is_revoked = True
        if s.refresh_jti:
            block_refresh(user, s.refresh_jti, 7*24*3600)
        s.save()
    return True

def save_signin_session(user: User, refresh_jti: str | None, device_info: str | None, user_agent: str | None, ip: str | None):
    DeviceSession(
        user=user, refresh_jti=refresh_jti, device_info=device_info,
        user_agent=user_agent, ip_address=ip, last_seen_at=datetime.now(timezone.utc)
    ).save()

def create_password_reset(user: User, token: str, ttl_hours = 1) -> PasswordReset:
    return PasswordReset(user=user, token=token, expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).save()

def get_valid_password_reset(token: str) -> Optional[PasswordReset]:
    return PasswordReset.objects(token=token, expires_at__gt=datetime.now(timezone.utc)).first()

def mark_password_reset_used(rec: PasswordReset):
    rec.used = True
    rec.save()

def create_email_verification(user: User, token: str, ttl_hours = 24) -> EmailVerification:
    return EmailVerification(user=user, token=token, expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).save()

def get_valid_email_verification(token: str) -> Optional[EmailVerification]:
    return EmailVerification.objects(token=token, expires_at__gt=datetime.now(timezone.utc)).first()

def mark_email_verification_used(rec: EmailVerification):
    rec.verified_at = datetime.now(timezone.utc)
    rec.save()