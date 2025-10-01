import secrets
import uuid
from datetime import datetime, timezone, timedelta

from .models_recovery import PasswordReset, EmailVerification
from .models_session import DeviceSession
from .models_token import TokenBlocklist
from ..users.models import User
from ...core.exceptions import AppError
from ...core.validation import require_fields
from ...core.security import hash_password, verify_password
from ...core.jwt_tools import issue_tokens
from ..users.repositories import UserRepo
from ..users.mappers import user_public

def __init__(self, user_repo: UserRepo | None = None):
    self.user_repo = user_repo

def _ensure_unique_account(self, username: str, email: str):
    if self.users.email_exists(email):
        raise AppError("Email already in use", 400)
    if self.users.username_exists(username):
        raise AppError("Username already in use", 400)

def _tokens_for_user(user):
    access, refresh = issue_tokens(str(user.id))
    return {
        "access_token": access,
        "refresh_token": refresh,
    }

def signup(self, payload: dict):
    require_fields(payload, "username", "email", "password")
    username = payload["username"].strip()
    email = payload["email"].strip().lower()
    password = payload["password"]

    self._ensure_unique_account(username, email)

    user = self.user_repo.create_user(
        username=username,
        email=email,
        password_hash=hash_password(password)
    )

    user.last_login_at = datetime.now(timezone.utc)
    user.save()

    data = {"user": user_public(user)} | self._tokens_for_user(user)
    return data

def signin(self, payload: dict):
    require_fields(payload, "email", "password")
    email = payload["email"].strip().lower()
    password = payload["password"]

    user = self.users.get_by_email(email)
    if not user:
        raise AppError("Invalid email or password", 400)
    if not verify_password(password, user.password_hash):
        raise AppError("Invalid email or password", 400)
    if not user.is_active:
        raise AppError("Account is not active", 403)

    user.last_login_at = datetime.now(timezone.utc)
    user.save()

    data = {"user": user_public(user)} | self._tokens_for_user(user)
    return data

def refresh_access(uid:str):
    access, _ = issue_tokens(uid)
    return {"access_token": access}

def signout(user: User, jti: str, ttl_seconds: int = 8 * 3600 ):
    TokenBlocklist.revoke(user, jti, "access", ttl_seconds)
    return True

def signout_all(user: User):
    for s in DeviceSession.objects(user=user, is_revoked=False):
        s.is_revoked = True
        if s.refresh_jti:
            TokenBlocklist.revoke(user, s.refresh_jti, "refresh", 7 * 24 * 3600)
        s.save()
    return True

def sessions(user: User):
    return[{
        "id": str(s.id),
        "device_name": s.device_name,
        "ip": s.ip_address,
        "last_seen_at": s.last_seen_at.isoformat(),
        "revoked": s.is_revoked
    } for s in DeviceSession.objects(user=user).order_by("-last_seen_at")]

def revoke_session(user: User, session_id: str):
    s = DeviceSession.objects(user=user, id=session_id).first()
    if not s:
        raise AppError("Session not found", 404)
    s.is_revoked = True
    if s.refresh_jti:
        TokenBlocklist.revoke(user, s.refresh_jti, "refresh", 7 * 24 * 3600)
    s.save()
    return True

def change_password(self, uid, payload: dict):
    require_fields(payload, "current_password", "new_password")
    u = self.users.get_by_email(self.users.get_by_id(uid).email) if hasattr(self.users, "get_by_id") else User.objects(id=uid).first()
    if not u:
        raise AppError("User not found", 404)
    if not verify_password(payload["old_password"], u.password_hash):
        raise AppError("Invalid password", 400)
    u.password_hash = hash_password(payload["new_password"])
    u.save()
    self.signout_all(u)
    return True

def forgot_password(self, email:str):
    u = self.users.get_by_email(email)
    if not u:
        return True
    token = uuid.uuid4().hex + secrets.token_hex(8)
    pr = PasswordReset(user=u, token=token, expires_at = datetime.now(timezone.utc)+timedelta(hours=1)).save()
    #TODO: send email '...?token=<token>'
    return True

def reset_password(self, token:str, new_password:str):
    rec = PasswordReset.objects(token = token, used=False, expires_at__gt=datetime.now(timezone.utc)).first()
    if not rec:
        raise AppError("Invalid token", 400)
    u = rec.user
    u.password_hash = hash_password(new_password)
    u.save()
    rec.used = True
    rec.save()
    self.signout_all(u)
    return True

def send_verify_email(self, email:str):
    u = self.users.get_by_email(email)
    if not u: return True
    token = uuid.uuid4().hex + secrets.token_hex(8)
    EmailVerification(user=u, token=token, expires_at = datetime.now(timezone.utc)+timedelta(hours=24)).save()
    #TODO: send email '...?token=<token>'
    return True

def verify_email(token:str):
    rec = EmailVerification.objects(token = token, used=False, expires_at__gt=datetime.now(timezone.utc)).first()
    if not rec:
        raise AppError("Invalid token", 400)
    u = rec.user
    u.is_active = True
    u.save()
    rec.verified_at = datetime.now(timezone.utc)
    return True