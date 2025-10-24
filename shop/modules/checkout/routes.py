from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ...core.responses import ok
from . import bp
from .services import s_complete_checkout, s_get_checkout, s_start_checkout
from ...core.utils import sanitize_session_id

SESSION_COOKIE_NAME = "session_id"


def _extract_session_id() -> str | None:
    cookie_candidate = sanitize_session_id(request.cookies.get(SESSION_COOKIE_NAME))
    if cookie_candidate:
        return cookie_candidate

    query_candidate = sanitize_session_id(request.args.get("session_id", type=str))
    if query_candidate:
        return query_candidate

    header_candidate = sanitize_session_id(request.headers.get("X-Session-Id"))
    if header_candidate:
        return header_candidate

    return None


@bp.post("")
@jwt_required(optional=True)
def r_start_checkout():
    payload = request.get_json(silent=True) or {}
    session_id = _extract_session_id()
    if session_id and "session_id" not in payload:
        payload = dict(payload)
        payload["session_id"] = session_id
    summary = s_start_checkout(get_jwt_identity(), payload)
    return ok(summary, "Checkout initialized successfully.")


@bp.get("/<checkout_id>")
@jwt_required(optional=True)
def r_get_checkout(checkout_id):
    session_id = _extract_session_id()
    summary = s_get_checkout(checkout_id, get_jwt_identity(), session_id)
    return ok(summary, "Checkout retrieved successfully.")


@bp.post("/<checkout_id>/complete")
@jwt_required(optional=True)
def r_complete_checkout(checkout_id):
    payload = request.get_json(silent=True) or {}
    session_id = _extract_session_id()
    if session_id and "session_id" not in payload:
        payload = dict(payload)
        payload["session_id"] = session_id
    summary = s_complete_checkout(checkout_id, get_jwt_identity(), payload)
    return ok(summary, "Checkout completed successfully.")