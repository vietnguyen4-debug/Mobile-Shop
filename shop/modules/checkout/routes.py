from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ...core.responses import ok
from . import bp
from .services import s_complete_checkout, s_get_checkout, s_start_checkout


@bp.post("")
@jwt_required(optional=True)
def r_start_checkout():
    payload = request.get_json(silent=True) or {}
    summary = s_start_checkout(get_jwt_identity(), payload)
    return ok(summary, "Checkout initialized successfully.")


@bp.get("/<checkout_id>")
@jwt_required(optional=True)
def r_get_checkout(checkout_id):
    session_id = request.args.get("session_id", type=str)
    summary = s_get_checkout(checkout_id, get_jwt_identity(), session_id)
    return ok(summary, "Checkout retrieved successfully.")


@bp.post("/<checkout_id>/complete")
@jwt_required(optional=True)
def r_complete_checkout(checkout_id):
    payload = request.get_json(silent=True) or {}
    summary = s_complete_checkout(checkout_id, get_jwt_identity(), payload)
    return ok(summary, "Checkout completed successfully.")