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
def r_get_user_public(user_id):
    return ok(s_get_user_public(user_id))

@bp.put("/users/<user_id>")
@jwt_required()
@self_or_admin("user_id")
def r_update_users(user_id):
    return ok(s_update_users(user_id, request.get_json() or {}))

@bp.get("/users/<user_id>/addresses")
@jwt_required()
@self_or_admin("user_id")
def r_list_addresses(user_id):
    return ok(s_list_addresses(user_id))

@bp.post("/users/<user_id>/addresses")
@jwt_required()
@self_or_admin("user_id")
def r_add_address(user_id):
    return created(s_add_address(user_id, request.get_json() or {}))

@bp.put("/users/<user_id>/addresses/<address_id>")
@jwt_required()
@self_or_admin("user_id")
def r_update_address(user_id, address_id):
    s_update_address(user_id, address_id, request.get_json() or {})
    return no_content()

@bp.delete("/users/<user_id>/addresses/<address_id>")
@jwt_required()
@self_or_admin("user_id")
def r_delete_address(user_id, address_id):
    s_delete_address(user_id, address_id)
    return no_content()

@bp.patch("/users/<user_id>/addresses/<address_id>/default")
@jwt_required()
@self_or_admin("user_id")
def r_set_default(user_id, address_id):
    s_set_default(user_id, address_id)
    return no_content()