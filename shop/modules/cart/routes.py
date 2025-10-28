from flask import request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from . import bp
from .services import (
    s_get_cart,
    s_add_item,
    s_update_item,
    s_remove_item,
    s_merge_cart_on_login,
)
from ...core.responses import ok, created
from ...core.exceptions import AppError

SESSION_COOKIE_NAME = "session_id"
SESSION_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days

def _get_cookie_settings() -> tuple[bool, str]:
    secure_default = current_app.config.get("CART_SESSION_COOKIE_SECURE", True)
    samesite_default = current_app.config.get("CART_SESSION_COOKIE_SAMESITE", "Lax")
    return bool(secure_default), samesite_default

def _sanitize_session_id(value: str | None) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed:
            return trimmed
    return None

def _attach_session_cookie(response, session_id: str | None):
    secure_default, samesite_default = _get_cookie_settings()
    cleaned_session = _sanitize_session_id(session_id)

    if cleaned_session:
        response.set_cookie(
            SESSION_COOKIE_NAME,
            cleaned_session,
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=True,
            samesite=samesite_default,
            secure=True if secure_default else request.is_secure,
            path="/",
        )
    elif request.cookies.get(SESSION_COOKIE_NAME):
        response.delete_cookie(
            SESSION_COOKIE_NAME,
            path="/",
            samesite=samesite_default,
            secure=True if secure_default else request.is_secure,
        )
    return response

def _extract_session_id() -> str | None:
    cookie_candidate = _sanitize_session_id(request.cookies.get(SESSION_COOKIE_NAME))
    if cookie_candidate:
        return cookie_candidate

    header_candidate = _sanitize_session_id(request.headers.get("X-Session-Id"))
    if header_candidate:
        return header_candidate

    return None


@bp.get("")
@jwt_required(optional=True)
def r_get_cart():
    uid = get_jwt_identity()
    session_id = _extract_session_id()
    result = s_get_cart(uid, session_id)
    response = ok(result, "Cart retrieved successfully.")
    # For logged-in users, do not set session cookie (delete if present)
    return _attach_session_cookie(response, None if uid else result.get("session_id"))


@bp.post("/items")
@jwt_required(optional=True)
def r_add_item():
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id()
    payload = dict(data)
    payload.pop("session_id", None)
    uid = get_jwt_identity()
    result = s_add_item(uid, session_id, payload)
    response = created(result, "Item added to cart successfully.")
    # For logged-in users, do not set session cookie (delete if present)
    return _attach_session_cookie(response, None if uid else result.get("session_id"))


@bp.patch("/items/<item_id>")
@jwt_required(optional=True)
def r_update_item(item_id):
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id()
    payload = dict(data)
    payload.pop("session_id", None)
    uid = get_jwt_identity()
    result = s_update_item(uid, session_id, item_id, payload)
    response = ok(result, "Cart item updated successfully.")
    # For logged-in users, do not set session cookie (delete if present)
    return _attach_session_cookie(response, None if uid else result.get("session_id"))


@bp.delete("/items/<item_id>")
@jwt_required(optional=True)
def r_remove_item(item_id):
    uid = get_jwt_identity()
    session_id = _extract_session_id()
    result = s_remove_item(uid, session_id, item_id)
    response = ok(result, "Cart item removed successfully.")
    # For logged-in users, do not set session cookie (delete if present)
    return _attach_session_cookie(response, None if uid else result.get("session_id"))


@bp.post("/merge")
@jwt_required()
def r_merge_cart():
    session_id = _extract_session_id()
    if not session_id:
        raise AppError("Session identifier required", 400, name="INVALID_SESSION")
    result = s_merge_cart_on_login(get_jwt_identity(), session_id)
    response = ok(result, "Cart merged successfully.")
    return _attach_session_cookie(response, result.get("session_id"))
