from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from . import bp
from .services import s_assign_shipment, s_get_shipment_for_checkout
from ...core.responses import ok


@bp.post("")
@jwt_required(optional=True)
def r_assign_shipment():
    data = request.get_json(silent=True) or {}
    shipment = s_assign_shipment(get_jwt_identity(), data)
    return ok(shipment, "Shipment information saved successfully.")


@bp.get("/checkout/<checkout_id>")
@jwt_required(optional=True)
def r_get_shipment(checkout_id):
    session_id = request.args.get("session_id", type=str)
    shipment = s_get_shipment_for_checkout(
        get_jwt_identity(), checkout_id, session_id
    )
    return ok(shipment, "Shipment retrieved successfully.")