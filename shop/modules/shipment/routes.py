from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from . import bp
from .services import s_assign_shipment, s_get_shipment_for_checkout, s_complete_shipment
from ...core.rbac import roles_required
from ...core.responses import ok
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
def r_assign_shipment():
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id()
    payload = dict(data)
    if session_id and "session_id" not in payload:
        payload["session_id"] = session_id
    shipment = s_assign_shipment(get_jwt_identity(), payload)
    return ok(shipment, "Shipment information saved successfully.")


@bp.get("/checkout/<checkout_id>")
@jwt_required(optional=True)
def r_get_shipment(checkout_id):
    session_id = _extract_session_id()
    shipment = s_get_shipment_for_checkout(
        get_jwt_identity(), checkout_id, session_id
    )
    return ok(shipment, "Shipment retrieved successfully.")

@bp.post("/<shipment_id>/complete")
@jwt_required()
@roles_required("admin")
def r_complete_shipment(shipment_id):
    shipment = s_complete_shipment(shipment_id)
    return ok(shipment, "Shipment marked as delivered.")