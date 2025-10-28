import re, unicodedata
from typing import Tuple, Any, Optional
from bson import ObjectId

from shop.core.exceptions import AppError
from shop.modules.checkout.models import Checkout
from shop.modules.users.models import User


def slugify(text: str, prefix: str | None = None) -> str:
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return f"{prefix}-{text}" if prefix else text

def parse_oid(oid: str):
    if not isinstance(oid, str): return None
    s = oid.strip()
    return ObjectId(s) if ObjectId.is_valid(s) else None

def parse_pagination(page: int | str | None, limit: int | str | None, *, max_limit=100) -> Tuple[int, int]:
    p = max(int(page or 1), 1)
    l = min(max(int(limit or 20), 1), max_limit)
    return p, l

def ensure_unique_slug(model, slug: str, *, field="slug"):
    from .exceptions import AppError
    if not slug:
        raise AppError("Slug required", 400)
    if model.objects(**{field: slug}).first():
        raise AppError("Slug already used", 409)

def resolve_by_slug_or_id(model, identifier: str):
    obj = model.objects(slug=identifier).first()
    if obj:
        return obj
    oid = parse_oid(identifier)
    return model.objects(id=oid).first() if oid else None

def load_checkout(checkout_id: Any) -> Checkout:
    if checkout_id is None:
        raise AppError("Checkout identifier is required", 400, name="INVALID_CHECKOUT")
    oid = parse_oid(str(checkout_id))
    if not oid:
        raise AppError("Invalid checkout identifier", 400, name="INVALID_CHECKOUT")
    try:
        checkout = Checkout.objects(id=oid).first()
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to load checkout: {str(exc)}", 500, name="DATABASE_ERROR"
        )
    if not checkout:
        raise AppError("Checkout not found", 404, name="CHECKOUT_NOT_FOUND")
    return checkout


def load_user(user_id: Optional[str]) -> Optional[User]:
    if not user_id:
        return None
    oid = parse_oid(str(user_id))
    if not oid:
        raise AppError("Invalid user identifier", 400, name="INVALID_USER")
    try:
        user = User.objects(id=oid).first()
    except Exception as exc:  # pragma: no cover - defensive
        raise AppError(
            f"Failed to load user: {str(exc)}", 500, name="DATABASE_ERROR"
        )
    if not user:
        raise AppError("User not found", 404, name="INVALID_USER")
    return user


def sanitize_session_id(session_id: Any) -> Optional[str]:
    if session_id is None:
        return None
    if not isinstance(session_id, str):
        raise AppError("Session identifier must be a string", 400, name="INVALID_SESSION")
    cleaned = session_id.strip()
    if not cleaned:
        return None
    if len(cleaned) > 120:
        raise AppError("Session identifier too long", 400, name="INVALID_SESSION")
    return cleaned

def _mark_guest_inactive(user: User) -> None:
    if getattr(user, "is_active", True):
        try:
            user.is_active = False
            user.save()
        except Exception:
            # Failing to persist the inactive flag should not leak
            # information or block guest checkout access.
            pass


def _is_guest_user(user: Optional[User]) -> bool:
    if not user:
        return False
    username = getattr(user, "username", "") or ""
    email = getattr(user, "email", "") or ""
    if username.startswith("guest_") and email.endswith("@guest.local"):
        _mark_guest_inactive(user)
        return True
    return False

def ensure_checkout_access(
    checkout: Checkout, user: Optional[User], session_id: Optional[str]
) -> None:
    checkout_user = getattr(checkout, "user", None)
    checkout_session = getattr(checkout, "session_id", None)
    guest_checkout = _is_guest_user(checkout_user)

    if user:
        if checkout_user and str(checkout_user.id) != str(user.id):
            raise AppError(
                "Checkout does not belong to the current user",
                403,
                name="CHECKOUT_FORBIDDEN",
            )
        if session_id and checkout_session and checkout_session != session_id:
            raise AppError(
                "Session identifier does not match checkout",
                403,
                name="CHECKOUT_FORBIDDEN",
            )
        return

    if checkout_user and not guest_checkout:
        raise AppError(
            "Checkout belongs to a user account",
            403,
            name="CHECKOUT_FORBIDDEN",
        )

    if not session_id:
        raise AppError(
            "Session identifier is required for guest checkout",
            400,
            name="INVALID_SESSION",
        )

    if checkout_session and checkout_session != session_id:
        raise AppError(
            "Session identifier does not match checkout",
            403,
            name="CHECKOUT_FORBIDDEN",
        )

def normalize_required_string(
    value: Any, *, field: str, code: str, max_length: int
) -> str:
    if not isinstance(value, str):
        raise AppError(f"{field} must be a string", 400, name=code)
    cleaned = value.strip()
    if not cleaned:
        raise AppError(f"{field} is required", 400, name=code)
    if len(cleaned) > max_length:
        raise AppError(f"{field} is too long", 400, name=code)
    return cleaned

