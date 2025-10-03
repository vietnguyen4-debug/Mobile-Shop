import secrets
import uuid
from datetime import datetime, timezone

from flask import current_app

from .models_recovery import PasswordReset, EmailVerification
from .repositories import block_access, revoke_all_sessions, create_password_reset, mark_password_reset_used, \
    create_email_verification, mark_email_verification_used, list_sessions, revoke_sessions
from ...core.exceptions import AppError
from ...core.validation import require_fields
from ...core.security import hash_password, verify_password
from ...core.jwt_tools import issue_tokens
from ..users.repositories import *
from ..users.mappers import user_public
from ...core.mailer import send_reset_password, send_verify_email

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
    user.last_login_at = datetime.now(timezone.utc)

    access_token, refresh_token = issue_tokens(str(user.id))
    return {
        "user": user_public(user),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

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

    user.last_login_at = datetime.now(timezone.utc)
    access_token, refresh_token = issue_tokens(str(user.id))
    return {
        "user": user_public(user),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

def s_refresh_access(uid: str):
    access, _ = issue_tokens(uid, access=1, refresh=7)
    return {"access_token": access}

def s_signout(user: User, jti: str):
    ttl = int(current_app.config.get("JWT_ACCESS_TTL_SECONDS", 8*3600))
    block_access(user, jti, ttl)
    return True

def s_signout_all(user: User):
    revoke_all_sessions(user)
    return True

def s_list_sessions(user: User):
    return[{
        "id": str(s.id),
        "device_info": s.device_info,
        "ip": s.ip_address,
        "last_seen_at": s.last_seen_at.isoformat(),
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
    email_verification = EmailVerification.objects(token=token, expires_at__gt=datetime.now(timezone.utc)).first()
    if not email_verification:
        raise AppError("Invalid token or expired token", 400)

    user = email_verification.user
    user.is_active = True
    user.save()
    mark_email_verification_used(email_verification)
    s_signout_all(user)
    return True

