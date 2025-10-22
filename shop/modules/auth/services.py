import secrets
import uuid
from datetime import datetime, timezone, timedelta

from flask import current_app, request, has_request_context
from flask_jwt_extended import decode_token

from .models_recovery import PasswordReset
from .repositories import (
    block_access,
    block_refresh,
    revoke_all_sessions,
    create_password_reset,
    mark_password_reset_used,
    create_email_verification,
    mark_email_verification_used,
    list_sessions,
    revoke_sessions,
    get_valid_email_verification,
    save_signin_session,
    get_session_by_refresh_jti,
    update_session_refresh,
)
from ...core.exceptions import AppError
from ...core.validation import require_fields
from ...core.security import hash_password, verify_password
from ...core.jwt_tools import issue_tokens
from ..users.repositories import *
from ..users.mappers import user_public
from ...core.mailer import send_reset_password, send_verify_email
from ..users.models import User

def _decode_refresh_jti(token: str | None) -> str | None:
    if not token:
        return None
    try:
        decoded = decode_token(token)
    except Exception:
        return None
    return decoded.get("jti")


def _get_client_ip() -> str | None:
    if not has_request_context():
        return None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr


def _normalize_device_context(device_hint: str | None = None) -> tuple[str, str | None, str | None]:
    ua = None
    if has_request_context():
        ua = request.headers.get("User-Agent")
        if not device_hint:
            device_hint = request.user_agent.string
    device_info = (device_hint or "").strip() or (ua or "Unknown device")
    return device_info, ua, _get_client_ip()

def _access_block_ttl() -> int:
    override = current_app.config.get("JWT_ACCESS_TTL_SECONDS")
    if override is not None:
        try:
            ttl = int(override)
            if ttl > 0:
                return ttl
        except (TypeError, ValueError):
            pass
    access_cfg = current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES", timedelta(days=1))
    if isinstance(access_cfg, timedelta):
        ttl = int(access_cfg.total_seconds())
    else:
        try:
            ttl = int(access_cfg)
        except (TypeError, ValueError):
            ttl = 24 * 3600
    return max(ttl, 1)


def _persist_session(user: User, refresh_token: str, device_hint: str | None = None):
    refresh_jti = _decode_refresh_jti(refresh_token)
    if not refresh_jti:
        return
    device_info, user_agent, ip = _normalize_device_context(device_hint)
    save_signin_session(user, refresh_jti, device_info, user_agent, ip)

def _set_up_user(user: User, payload: dict):
    user.last_login_at = datetime.now(timezone.utc)
    access_token, refresh_token = issue_tokens(str(user.id), role=user.role)
    _persist_session(user, refresh_token, payload.get("device_info"))
    session_id = (payload.get("session_id") or "").strip()
    if session_id:
        try:
            from ..cart.services import s_merge_cart_on_login
            s_merge_cart_on_login(str(user.id), session_id)
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"Failed to merge guest cart: {str(e)}", 500, name="CART_MERGE_ERROR")
    return {
        "user": user_public(user),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def s_signup(payload: dict):
    require_fields(payload, "username", "email", "password")
    username = payload["username"].strip()
    email = payload["email"].strip().lower()
    password = payload["password"]

    if email_exists(email):
        raise AppError("Email already exists", 409)
    if username_exists(username):
        raise AppError("Username already exists", 409)

    user = create_user(username, email, hash_password(password))
    return _set_up_user(user, payload)

def s_signin(payload: dict):
    require_fields(payload, "email", "password")
    email = payload["email"].strip().lower()
    password = payload["password"]

    user = get_by_email(email)
    if not user:
        raise AppError("Invalid email or password", 401)
    if not verify_password(password, user.password_hash):
        raise AppError("Invalid email or password", 401)
    if not user.is_active:
        raise AppError("Account is not active", 403)

    return _set_up_user(user, payload)

def s_refresh_access(uid: str, refresh_jti: str | None):
    user = User.objects(id=uid).first()
    if not user:
        raise AppError("Invalid user", 404)
    if not refresh_jti:
        raise AppError("Invalid refresh token", 401)

    session = get_session_by_refresh_jti(user, refresh_jti)
    if not session or session.is_revoked:
        block_refresh(user, refresh_jti)
        raise AppError("Session has been revoked", 401)

    access_token, refresh_token = issue_tokens(str(user.id), role=user.role)
    new_refresh_jti = _decode_refresh_jti(refresh_token)
    if not new_refresh_jti:
        block_refresh(user, refresh_jti)
        raise AppError("Failed to rotate refresh token", 500)

    payload = request.get_json(silent=True) if has_request_context() else None
    device_hint = payload.get("device_info") if isinstance(payload, dict) else None
    device_info, user_agent, ip = _normalize_device_context(device_hint)

    block_refresh(user, refresh_jti)
    update_session_refresh(session, new_refresh_jti, device_info, user_agent, ip)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

def s_signout(
    user: User,
    access_jti: str,
    refresh_token: str | None = None,
    refresh_jti: str | None = None,
    session_id: str | None = None,
):
    if not user:
        raise AppError("Invalid user", 404)

    if session_id:
        revoked = revoke_sessions(user, session_id)
        if not revoked:
            raise AppError("Invalid session", 404)
    else:
        refresh_identifier = refresh_jti or _decode_refresh_jti(refresh_token)
        if refresh_identifier:
            block_refresh(user, refresh_identifier)
            session = get_session_by_refresh_jti(user, refresh_identifier)
            if session:
                session.is_revoked = True
                session.last_seen_at = datetime.now(timezone.utc)
                session.save()
            revoked = True
        else:
            raise AppError("Refresh token or session identifier required", 400)

    block_access(user, access_jti, _access_block_ttl())
    return revoked

def s_signout_all(user: User):
    revoke_all_sessions(user)
    return True

def s_list_sessions(user: User):
    return[{
        "id": str(s.id),
        "device_info": s.device_info,
        "user_agent": s.user_agent,
        "ip": s.ip_address,
        "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else None,
        "revoked": s.is_revoked,
    } for s in list_sessions(user)]

def s_revoke_session(user: User, sid: str):
    ok = revoke_sessions(user, sid)
    if not ok:
        raise AppError("Invalid session", 404)
    return True

def s_change_password(uid: str, payload: dict):
    require_fields(payload, ["old_password", "new_password"])
    user = User.objects(id=uid).first()
    if not user:
        raise AppError("Invalid user", 404)
    if not verify_password(payload["old_password"], user.password_hash):
        raise AppError("Invalid old password", 400)
    user.password_hash = hash_password(payload["new_password"])
    s_signout_all(user)
    user.save()

def s_forgot_password(email: str):
    user = get_by_email(email)
    if not user:
        return True

    token = uuid.uuid4().hex + secrets.token_hex(16)
    create_password_reset(user, token, ttl_hours=1)
    send_reset_password(user.email, token)
    return True

def s_reset_password(token: str, new_password: str):
    reset = PasswordReset.objects(token=token, expires_at__gt=datetime.now(timezone.utc)).first()
    if not reset:
        raise AppError("Invalid token or expired token", 400)

    user = reset.user
    user.password_hash = hash_password(new_password)
    reset.save()
    mark_password_reset_used(reset)
    user.save()
    s_signout_all(user)
    return True

def s_send_verify(email: str):
    user = get_by_email(email)
    if not user: return True
    token = uuid.uuid4().hex + secrets.token_hex(16)
    create_email_verification(user, token, ttl_hours=24)
    send_verify_email(user.email, token)
    return True

def s_verify_email(token: str):
    rec = get_valid_email_verification(token)
    if not rec:
        raise AppError("Invalid or expired token", 400)
    u = rec.user
    if rec.new_email:
        from ..users.repositories import email_exists
        if email_exists(rec.new_email):
            raise AppError("Email already used", 409)
        u.email = rec.new_email
        u.email_verified = True
    else:
        u.email_verified = True
    u.save()
    mark_email_verification_used(rec)
    return True

