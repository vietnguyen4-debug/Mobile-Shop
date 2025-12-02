from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ...core.rbac import roles_required
from ...core.responses import created, ok
from ...core.exceptions import AppError
from ...core.utils import sanitize_session_id
from . import bp, bp_admin
from .services import (
    s_complete_offline_payment,
    s_create_offline_payment,
    s_get_payment,
    s_list_payments_by_checkout,
)

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


@bp.get("")
@jwt_required(optional=True)
def r_list_payments():
    checkout_id = request.args.get("checkout_id", type=str)
    if not checkout_id:
        raise AppError("checkout_id query parameter is required", 400, name="INVALID_CHECKOUT")
    session_id = _extract_session_id()
    payments = s_list_payments_by_checkout(get_jwt_identity(), session_id, checkout_id)
    return ok(payments, "Payments retrieved successfully.")


@bp.get("/<payment_id>")
@jwt_required(optional=True)
def r_get_payment(payment_id):
    session_id = _extract_session_id()
    payment = s_get_payment(payment_id, get_jwt_identity(), session_id)
    return ok(payment, "Payment retrieved successfully.")


@bp_admin.post("/offline")
@jwt_required()
@roles_required("admin")
def r_create_offline_payment():
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id()
    if session_id and "session_id" not in data:
        data = dict(data)
        data["session_id"] = session_id
    payment = s_create_offline_payment(get_jwt_identity(), data)
    return created(payment, "Offline payment created successfully.")


@bp_admin.post("/<payment_id>/complete")
@jwt_required()
@roles_required("admin")
def r_complete_offline_payment(payment_id):
    data = request.get_json(silent=True) or {}
    payment = s_complete_offline_payment(payment_id, data)
    return ok(payment, "Payment marked as completed.")
