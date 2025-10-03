from ...core.exceptions import AppError
from ...core.validation import require_fields
from .repositories import *

def s_get_me(uid: str):
    data = get_public_by_id(uid)
    if not data:
        raise AppError("User not found", 404)
    return data

def s_get_user_public(uid: str):
    data = get_public_by_id(uid)
    if not data:
        raise AppError("User not found", 404)
    return data

def s_update_users(uid:str, payload: dict):
    out = update_user(uid, payload.get("first_name"), payload.get("last_name"), payload.get("phone"), payload.get("avatar"))
    if not out: raise AppError("User not found", 404)
    return out

def s_list_addresses(uid:str):
    out = list_addresses(uid)
    if out is None: raise AppError("User not found", 404)
    return out

def s_add_address(uid:str, payload: dict):
    require_fields(payload, "address_line", "city")
    out = add_address(uid, payload["address_line"], payload["city"], payload.get("is_default"))
    if out is None: raise AppError("User not found", 404)
    return out

def s_update_address(uid:str, addr_id: str, payload: dict):
    ok = update_address(uid, addr_id, payload.get("address_line"), payload.get("city"), payload.get("is_default"))
    if ok is None: raise AppError("User not found", 404)
    if not ok: raise AppError("Address not found", 404)
    return True

def s_delete_address(uid:str, addr_id: str):
    ok = delete_address(uid, addr_id)
    if ok is None: raise AppError("User not found", 404)
    if not ok: raise AppError("Address not found", 404)
    return True

def s_set_default(uid:str, addr_id: str):
    ok = set_default(uid, addr_id)
    if ok is None: raise AppError("User not found", 404)
    if not ok: raise AppError("Address not found", 404)
    return True