import logging
from flask import request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from . import bp
from .services import (
    s_get_cart,
    s_add_item,
    s_update_item,
    s_merge_cart_on_login,
)
from ...core.responses import ok, created
from ...core.exceptions import AppError

SESSION_COOKIE_NAME = "session_id"
SESSION_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # fallback: 30 days

_session_logger = logging.getLogger("shop.cart.session")

def _get_cookie_settings() -> tuple[bool, str]:
    secure_default = current_app.config.get("CART_SESSION_COOKIE_SECURE", True)
    samesite_default = current_app.config.get("CART_SESSION_COOKIE_SAMESITE", "Lax")
    return bool(secure_default), samesite_default


def _get_cookie_max_age() -> int:
    return int(current_app.config.get("CART_SESSION_COOKIE_MAX_AGE_SECONDS", SESSION_COOKIE_MAX_AGE))

def _sanitize_session_id(value: str | None) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed:
            return trimmed
    return None

def _attach_session_cookie(response, session_id: str | None, *, refresh_existing: bool = True):
    secure_default, samesite_default = _get_cookie_settings()
    cleaned_session = _sanitize_session_id(session_id)
    current_cookie = _sanitize_session_id(request.cookies.get(SESSION_COOKIE_NAME))

    if cleaned_session:
        should_set_cookie = refresh_existing or current_cookie != cleaned_session
        if should_set_cookie:
            response.set_cookie(
                SESSION_COOKIE_NAME,
                cleaned_session,
                max_age=_get_cookie_max_age(),
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

def _mask_session_id(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 12:
        return value
    return f"{value[:8]}...{value[-4:]}"

def _extract_session_id() -> str | None:
    header_candidate = _sanitize_session_id(request.headers.get("X-Session-Id"))
    if header_candidate:
        return header_candidate

    query_candidate = _sanitize_session_id(request.args.get("session_id", type=str))
    if query_candidate:
        return query_candidate

    cookie_candidate = _sanitize_session_id(request.cookies.get(SESSION_COOKIE_NAME))
    if cookie_candidate:
        return cookie_candidate

    return None

def _maybe_log_session_debug(chosen: str | None, chosen_source: str | None):
    if not current_app.config.get("CART_SESSION_DEBUG", False):
        return

    raw_cookie = request.headers.get("Cookie")
    parsed_cookie = _sanitize_session_id(request.cookies.get(SESSION_COOKIE_NAME))
    header_candidate = _sanitize_session_id(request.headers.get("X-Session-Id"))
    query_candidate = _sanitize_session_id(request.args.get("session_id", type=str))

    _session_logger.info(
        "cart session resolve",
        extra={
            "path": request.path,
            "method": request.method,
            "cookie_raw": raw_cookie,
            "cookie_parsed": _mask_session_id(parsed_cookie),
            "header": _mask_session_id(header_candidate),
            "query": _mask_session_id(query_candidate),
            "chosen_source": chosen_source,
            "chosen": _mask_session_id(chosen),
        },
    )


@bp.get("")
@jwt_required(optional=True)
def r_get_cart():
    uid = get_jwt_identity()
    session_id = _extract_session_id()
    _maybe_log_session_debug(session_id, "resolved")
    result = s_get_cart(uid, session_id)
    response = ok(result, "Cart retrieved successfully.")
    # For guests, do not continuously refresh cookie TTL on read-only requests.
    return _attach_session_cookie(
        response,
        None if uid else result.get("session_id"),
        refresh_existing=False,
    )


@bp.post("/items")
@jwt_required(optional=True)
def r_add_item():
    data = request.get_json(silent=True) or {}
    body_session_id = _sanitize_session_id(data.get("session_id"))
    session_id = body_session_id or _extract_session_id()
    _maybe_log_session_debug(session_id, "body" if body_session_id else "resolved")
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
    body_session_id = _sanitize_session_id(data.get("session_id"))
    session_id = body_session_id or _extract_session_id()
    _maybe_log_session_debug(session_id, "body" if body_session_id else "resolved")
    payload = dict(data)
    payload.pop("session_id", None)
    quantity_value = payload.get("quantity")
    removal_requested = False
    try:
        if quantity_value is not None and int(quantity_value) <= 0:
            removal_requested = True
    except (TypeError, ValueError):
        removal_requested = False
    uid = get_jwt_identity()
    result = s_update_item(uid, session_id, item_id, payload)
    target_id = str(item_id)
    items = result.get("items", []) or []
    removed = removal_requested or not any(str(it.get("id")) == target_id for it in items)
    if not removed and result.get("total_quantity", 0) == 0:
        removed = True
    message = "Cart item removed successfully." if removed else "Cart item updated successfully."
    response = ok(result, message)
    # For logged-in users, do not set session cookie (delete if present)
    return _attach_session_cookie(response, None if uid else result.get("session_id"))


@bp.post("/merge")
@jwt_required()
def r_merge_cart():
    data = request.get_json(silent=True) or {}
    body_session_id = _sanitize_session_id(data.get("session_id"))
    session_id = body_session_id or _extract_session_id()
    _maybe_log_session_debug(session_id, "body" if body_session_id else "resolved")
    if not session_id:
        raise AppError("Session identifier required", 400, name="INVALID_SESSION")
    result = s_merge_cart_on_login(get_jwt_identity(), session_id)
    response = ok(result, "Cart merged successfully.")
    return _attach_session_cookie(response, result.get("session_id"))
