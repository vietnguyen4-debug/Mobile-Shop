import secrets
import uuid

from .repositories import _get_user
from ..auth.repositories import create_email_verification
from ...core.exceptions import AppError
from ...core.validation import require_fields
from .repositories import *

def s_get_me(uid: str):
    data = get_public_by_id(uid)
    if not data:
        raise AppError("User not found", 404, name="INVALID_USER")
    return data

def s_get_user_public(uid: str):
    data = get_public_by_id(uid)
    if not data:
        raise AppError("User not found", 404, name="INVALID_USER")
    return data

def s_update_users(uid:str, payload: dict):
    out = update_user(uid, payload.get("first_name"), payload.get("last_name"), payload.get("phone"), payload.get("avatar"))
    if not out: raise AppError("User not found", 404, name="INVALID_USER")
    return out

def s_list_addresses(uid:str):
    out = list_addresses(uid)
    if out is None: raise AppError("User not found", 404, name="INVALID_USER")
    return out

def s_add_address(uid:str, payload: dict):
    require_fields(payload, "address_line", "city")
    out = add_address(uid, payload["address_line"], payload["city"], payload.get("is_default"))
    if out is None: raise AppError("User not found", 404, name="INVALID_USER")
    return out

def s_update_address(uid:str, addr_id: str, payload: dict):
    ok = update_address(uid, addr_id, payload.get("address_line"), payload.get("city"), payload.get("is_default"))
    if ok is None: raise AppError("User not found", 404, name="INVALID_USER")
    if not ok: raise AppError("Address not found", 404, name="INVALID_ADDRESS")
    return True

def s_delete_address(uid:str, addr_id: str):
    ok = delete_address(uid, addr_id)
    if ok is None: raise AppError("User not found", 404, name="INVALID_USER")
    if not ok: raise AppError("Address not found", 404, name="INVALID_ADDRESS")
    return True

def s_set_default(uid:str, addr_id: str):
    ok = set_default(uid, addr_id)
    if ok is None: raise AppError("User not found", 404, name="INVALID_USER")
    if not ok: raise AppError("Address not found", 404, name="INVALID_ADDRESS")
    return True

def request_change_email(uid: str, payload: dict):
    require_fields(payload, "new_email")
    new_email = payload["new_email"].strip().lower()

    u = _get_user(uid)
    if not u: raise AppError("User not found", 404, name="INVALID_USER")

    if new_email == (u.email or "").lower():
        raise AppError("New email must be different", 422, name="INVALID_EMAIL")

    if email_exists(new_email):
        raise AppError("Email already used", 409, name="EMAIL_USED")

    token = uuid.uuid4().hex + secrets.token_hex(8)
    create_email_verification(u, token, ttl_hours=24, new_email=new_email)

    from ...core.mailer import send_verify_email
    send_verify_email(new_email, token)

    return True
