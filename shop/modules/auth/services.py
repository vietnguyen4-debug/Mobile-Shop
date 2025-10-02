import secrets
import uuid
from datetime import datetime, timezone, timedelta

from flask import current_app

from .models_recovery import PasswordReset, EmailVerification
from .models_session import DeviceSession
from .models_token import TokenBlocklist
from ...core.exceptions import AppError
from ...core.validation import require_fields
from ...core.security import hash_password, verify_password
from ...core.jwt_tools import issue_tokens
from ..users.repositories import *
from ..users.mappers import user_public
from ...core.mailer import send_reset_password, send_verify_email

def signup(payload: dict):
    require_fields(payload, ["username", "email", "password"])
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

def signin(payload: dict):
    require_fields(payload, ["email", "password"])
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

def refresh_access(uid: str):
    access, _ = issue_tokens(uid, access=1, refresh=7)
    return {"access_token": access}

def signout(user: User, jti: str):
    ttl = int(current_app.config.get("JWT_ACCESS_TTL_SECONDS", 8*3600))
    TokenBlocklist.revoke(user, jti,"access", ttl)
    return True

def signout_all(user: User):
    for s in DeviceSession.objects(user=user, is_revoked=False):
        s.is_revoked = True
        if s.refresh_jti:
            TokenBlocklist.revoke(user, s.refresh_jti, "refresh", 7*24*3600)
        s.save()
    return True

def list_sessions(user: User):
    return[{
        "id": str(s.id),
        "device_info": s.device_info,
        "ip": s.ip_address,
        "last_seen_at": s.last_seen_at.isoformat(),
        "revoked": s.is_revoked,
    } for s in DeviceSession.objects(user=user, is_revoked=False)]

def revoke_session(user: User, sid: str):
    s = DeviceSession.objects(user=user, id=sid).first()
    if not s:
        raise AppError("Session not found", 404)
    s.is_revoked = True
    if s.refresh_jti:
        TokenBlocklist.revoke(user, s.refresh_jti, "refresh", 7*24*3600)
    s.save()
    return True

def change_password(uid: str, payload: dict):
    require_fields(payload, ["old_password", "new_password"])
    user = User.objects(id=uid).first()
    if not user:
        raise AppError("Invalid user", 404)
    if not verify_password(payload["old_password"], user.password_hash):
        raise AppError("Invalid old password", 400)
    user.password_hash = hash_password(payload["new_password"])
    signout_all(user)
    user.save()

def forgot_password(email: str):
    user = get_by_email(email)
    if not user:
        return True

    token = uuid.uuid4().hex + secrets.token_hex(16)
    PasswordReset(user=user, token=token, expires_at = datetime.now(timezone.utc) + timedelta(hours=1)).save()
    send_reset_password(email, token)
    return True

def reset_password(token: str, new_password: str):
    reset = PasswordReset.objects(token=token, expires_at__gt=datetime.now(timezone.utc)).first()
    if not reset:
        raise AppError("Invalid token or expired token", 400)

    user = reset.user
    user.password_hash = hash_password(new_password)
    reset.used = True
    reset.save()
    signout_all(user)
    return True

def send_verify(email: str):
    user = get_by_email(email)
    if not user: return True
    token = uuid.uuid4().hex + secrets.token_hex(16)
    EmailVerification(user=user, token=token, expires_at = datetime.now(timezone.utc) + timedelta(hours=1)).save()
    send_verify_email(email, token)
    return True

def verify_email(token: str):
    email_verification = EmailVerification.objects(token=token, expires_at__gt=datetime.now(timezone.utc)).first()
    if not email_verification:
        raise AppError("Invalid token or expired token", 400)

    user = email_verification.user
    user.is_active = True
    user.save()
    email_verification.verified_at = datetime.now(timezone.utc)
    email_verification.save()
    return True

