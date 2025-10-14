from flask import request
from flask_jwt_extended import jwt_required
from . import bp
from .services import *
from ...core.responses import ok, created, no_content
from ...core.rbac import *


@bp.get("/me")
@jwt_required()
def r_get_me():
    uid = get_jwt_identity()
    return ok(s_get_me(uid))

@bp.get("/users/<user_id>")
@jwt_required()
@self_or_admin("user_id")
def r_get_user_public(user_id):
    return ok(s_get_user_public(user_id))

@bp.put("/users/<user_id>")
@jwt_required()
@self_or_admin("user_id")
def r_update_users(user_id):
    return ok(s_update_users(user_id, request.get_json() or {}), "User updated successfully.")

@bp.get("/users/<user_id>/addresses")
@jwt_required()
@self_or_admin("user_id")
def r_list_addresses(user_id):
    return ok(s_list_addresses(user_id), "User addresses listed successfully.")

@bp.post("/users/<user_id>/addresses")
@jwt_required()
@self_or_admin("user_id")
def r_add_address(user_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AppError("Body must be a JSON object", 400)
    return created(s_add_address(user_id, data), "Address added successfully.")

@bp.put("/users/<user_id>/addresses/<address_id>")
@jwt_required()
@self_or_admin("user_id")
def r_update_address(user_id, address_id):
    s_update_address(user_id, address_id, request.get_json() or {})
    return no_content("Address updated successfully.")

@bp.delete("/users/<user_id>/addresses/<address_id>")
@jwt_required()
@self_or_admin("user_id")
def r_delete_address(user_id, address_id):
    s_delete_address(user_id, address_id)
    return no_content("Address deleted successfully.")

@bp.patch("/users/<user_id>/addresses/<address_id>/default")
@jwt_required()
@self_or_admin("user_id")
def r_set_default(user_id, address_id):
    s_set_default(user_id, address_id)
    return no_content("Address set as default successfully.")

@bp.post("/users/<user_id>/change-email")
@jwt_required()
@self_or_admin("user_id")
def r_change_email(user_id):
    request_change_email(user_id, request.get_json() or {})
    return no_content("Email changed successfully.")