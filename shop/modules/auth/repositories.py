from datetime import datetime, timezone, timedelta
from typing import Optional
from flask import current_app
from .models_token import TokenBlocklist
from .models_session import DeviceSession
from .models_recovery import PasswordReset, EmailVerification
from ..users.models import User

def block_access(user: User, jti: str, ttl_seconds: int) -> TokenBlocklist:
    return TokenBlocklist.revoke(user, jti, "access", ttl_seconds)

def _refresh_ttl_seconds() -> int:
    cfg = current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES", timedelta(days=7))
    if isinstance(cfg, timedelta):
        return int(cfg.total_seconds())
    try:
        return int(cfg)
    except (TypeError, ValueError):
        return 7 * 24 * 3600

def block_refresh(user: User, jti: str, ttl_seconds: int | None = None) -> TokenBlocklist:
    ttl = ttl_seconds if ttl_seconds is not None else _refresh_ttl_seconds()
    return TokenBlocklist.revoke(user, jti, "refresh", ttl)

def _is_revoked(jti: str) -> bool:
    return TokenBlocklist.objects(jti=jti, revoked=True).first() is not None

def list_sessions(user: User) ->list[DeviceSession]:
    return list(DeviceSession.objects(user=user).order_by("-last_seen_at"))

def get_session_by_refresh_jti(user: User, refresh_jti: str) -> Optional[DeviceSession]:
    return DeviceSession.objects(user=user, refresh_jti=refresh_jti).first()

def update_session_refresh(session: DeviceSession, new_refresh_jti: str, device_info: str | None,
                           user_agent: str | None, ip: str | None) -> DeviceSession:
    session.refresh_jti = new_refresh_jti
    if device_info:
        session.device_info = device_info
    elif user_agent and not session.device_info:
        session.device_info = user_agent
    if user_agent:
        session.user_agent = user_agent
    if ip:
        cleaned_ip = ip.strip()
        session.ip_address = cleaned_ip or session.ip_address
    session.last_seen_at = datetime.now(timezone.utc)
    session.is_revoked = False
    session.save()
    return session

def revoke_sessions(user: User, session_id: str) -> bool:
    s = DeviceSession.objects(user=user, id=session_id).first()
    if not s: return False
    s.is_revoked = True
    if s.refresh_jti:
        block_refresh(user, s.refresh_jti)
    s.save()
    return True

def revoke_all_sessions(user: User) -> bool:
    for s in DeviceSession.objects(user=user, is_revoked=False):
        s.is_revoked = True
        if s.refresh_jti:
            block_refresh(user, s.refresh_jti)
        s.save()
    return True

def save_signin_session(user: User, refresh_jti: str | None, device_info: str | None, user_agent: str | None, ip: str | None):
    if not refresh_jti:
        return None
    info = (device_info or "").strip()
    ua = user_agent or None
    if not info:
        info = ua or "Unknown device"
    ip_value = (ip or "").strip() or None
    session = DeviceSession.objects(refresh_jti=refresh_jti).first()
    if not session:
        session = DeviceSession(user=user, refresh_jti=refresh_jti)
    session.user = user
    session.device_info = info
    session.user_agent = ua
    if ip_value is not None:
        session.ip_address = ip_value
    session.last_seen_at = datetime.now(timezone.utc)
    session.is_revoked = False
    session.save()
    return session

def create_password_reset(user: User, token: str, ttl_hours = 1) -> PasswordReset:
    return PasswordReset(user=user, token=token, expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).save()

def get_valid_password_reset(token: str) -> Optional[PasswordReset]:
    return PasswordReset.objects(token=token, expires_at__gt=datetime.now(timezone.utc)).first()

def mark_password_reset_used(rec: PasswordReset):
    rec.used = True
    rec.save()

def create_email_verification(user: User, token: str, ttl_hours=24, new_email: str | None = None) -> EmailVerification:
    return EmailVerification(
        user=user, token=token, new_email=new_email,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    ).save()

def get_valid_email_verification(token: str) -> Optional[EmailVerification]:
    return EmailVerification.objects(token=token, expires_at__gt=datetime.now(timezone.utc)).first()

def mark_email_verification_used(rec: EmailVerification):
    rec.verified_at = datetime.now(timezone.utc)
    rec.save()