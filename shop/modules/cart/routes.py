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



def _extract_session_id(data: dict | None = None) -> str | None:
    header_names = ("Session-ID", "Session-Id", "X-Session-Id")
    header_value = None
    for name in header_names:
        candidate = request.headers.get(name)
        if candidate:
            header_value = candidate
            break
    candidates = [
        request.cookies.get(SESSION_COOKIE_NAME),
        header_value,
        request.args.get(SESSION_COOKIE_NAME),
    ]
    if data:
        candidates.append(data.get(SESSION_COOKIE_NAME))
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
    return ok(s_get_cart(uid, session_id), "Cart retrieved successfully.")


@bp.post("/items")
@jwt_required(optional=True)
def r_add_item():
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id(data)
    payload = dict(data)
    payload.pop(SESSION_COOKIE_NAME, None)
    return created(s_add_item(get_jwt_identity(), session_id, payload), "Item added to cart successfully.")


@bp.patch("/items/<item_id>")
@jwt_required(optional=True)
def r_update_item(item_id):
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id(data)
    payload = dict(data)
    payload.pop(SESSION_COOKIE_NAME, None)
    return ok(s_update_item(get_jwt_identity(), session_id, item_id, payload), "Cart item updated successfully.")


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
    return ok(result, "Cart merged successfully.")