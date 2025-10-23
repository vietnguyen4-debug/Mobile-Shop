from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from ...core.rbac import roles_required
from . import bp
from .services import (
    s_complete_offline_payment,
    s_create_offline_payment,
    s_get_payment,
    s_list_payments_by_checkout,
)
from ...core.exceptions import AppError
from ...core.responses import created, ok


@bp.get("")
@jwt_required()
@roles_required("admin")
def r_list_payments():
    checkout_id = request.args.get("checkout_id", type=str)
    if not checkout_id:
        raise AppError("checkout_id query parameter is required", 400, name="INVALID_CHECKOUT")
    payments = s_list_payments_by_checkout(checkout_id)
    return ok(payments, "Payments retrieved successfully.")


@bp.get("/<payment_id>")
@jwt_required()
@roles_required("admin")
def r_get_payment(payment_id):
    payment = s_get_payment(payment_id)
    return ok(payment, "Payment retrieved successfully.")


@bp.post("/offline")
@jwt_required()
@roles_required("admin")
def r_create_offline_payment():
    data = request.get_json(silent=True) or {}
    payment = s_create_offline_payment(get_jwt_identity(), data)
    return created(payment, "Offline payment created successfully.")


@bp.post("/<payment_id>/complete")
@jwt_required()
@roles_required("admin")
def r_complete_offline_payment(payment_id):
    data = request.get_json(silent=True) or {}
    payment = s_complete_offline_payment(payment_id, data)
    return ok(payment, "Payment marked as completed.")