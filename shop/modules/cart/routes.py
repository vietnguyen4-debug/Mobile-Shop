from flask import request
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

def _attach_session_cookie(response, session_id: str | None):
    if session_id:
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_id,
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure,
        )
    elif request.cookies.get(SESSION_COOKIE_NAME):
        response.delete_cookie(SESSION_COOKIE_NAME)
    return response

def _extract_session_id(data: dict | None = None) -> str | None:
    candidates = [
        request.headers.get("X-Session-Id"),
        request.args.get("session_id"),
        request.cookies.get(SESSION_COOKIE_NAME),
    ]
    if data:
        candidates.append(data.get("session_id"))
    for candidate in candidates:
        if isinstance(candidate, str):
            value = candidate.strip()
            if value:
                return value
    return None


@bp.get("")
@jwt_required(optional=True)
def r_get_cart():
    uid = get_jwt_identity()
    session_id = _extract_session_id()
    result = s_get_cart(uid, session_id)
    response = ok(result, "Cart retrieved successfully.")
    return _attach_session_cookie(response, result.get("session_id"))


@bp.post("/items")
@jwt_required(optional=True)
def r_add_item():
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id(data)
    payload = dict(data)
    payload.pop("session_id", None)
    result = s_add_item(get_jwt_identity(), session_id, payload)
    response = created(result, "Item added to cart successfully.")
    return _attach_session_cookie(response, result.get("session_id"))


@bp.patch("/items/<item_id>")
@jwt_required(optional=True)
def r_update_item(item_id):
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id(data)
    payload = dict(data)
    payload.pop("session_id", None)
    result = s_update_item(get_jwt_identity(), session_id, item_id, payload)
    response = ok(result, "Cart item updated successfully.")
    return _attach_session_cookie(response, result.get("session_id"))


@bp.delete("/items/<item_id>")
@jwt_required(optional=True)
def r_remove_item(item_id):
    session_id = _extract_session_id()
    return ok(s_remove_item(get_jwt_identity(), session_id, item_id), "Cart item removed successfully.")


@bp.post("/merge")
@jwt_required()
def r_merge_cart():
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id(data)
    if not session_id:
        raise AppError("Session identifier required", 400, name="INVALID_SESSION")
    result = s_merge_cart_on_login(get_jwt_identity(), session_id)
    response = ok(result, "Cart merged successfully.")
    return _attach_session_cookie(response, result.get("session_id"))