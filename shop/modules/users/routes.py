from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from . import bp
from .services import *
from ...core.responses import ok, created, no_content


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
def r_update_users(user_id):
    uid = get_jwt_identity()
    return ok(s_update_users(user_id, request.get_json() or {}, uid))

@bp.get("/users/<user_id>/addresses")
@jwt_required()
def r_list_addresses(user_id):
    uid = get_jwt_identity()
    return ok(s_list_addresses(user_id, uid))

@bp.post("/users/<user_id>/addresses")
@jwt_required()
def r_add_address(user_id):
    uid = get_jwt_identity()
    return created(s_add_address(user_id, request.get_json() or {}, uid))

@bp.put("/users/<user_id>/addresses/<address_id>")
@jwt_required()
def r_update_address(user_id, address_id):
    uid = get_jwt_identity()
    s_update_address(user_id, address_id, request.get_json() or {}, uid)
    return no_content()

@bp.delete("/users/<user_id>/addresses/<address_id>")
@jwt_required()
def r_delete_address(user_id, address_id):
    uid = get_jwt_identity()
    s_delete_address(user_id, address_id, uid)
    return no_content()

@bp.patch("/users/<user_id>/addresses/<address_id>/default")
@jwt_required()
def r_set_default(user_id, address_id):
    uid = get_jwt_identity()
    s_set_default(user_id, address_id, uid)
    return no_content()