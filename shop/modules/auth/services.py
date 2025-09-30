from datetime import datetime, timezone
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

class AuthService:
    pass