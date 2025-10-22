from flask import request
from flask_jwt_extended import jwt_required

from . import bp
from .services import *
from ..users.models import User
from ...core.responses import ok, created, no_content
from ...core.rbac import *


@bp.post("/signup")
def r_signup():
    data = request.get_json() or {}
    return created(s_signup(data), "User created successfully.")

@bp.post("/signin")
def r_signin():
    data = request.get_json() or {}
    return ok(s_signin(data), "User signed in successfully.")

@bp.post("/refresh")
@jwt_required(refresh=True)
def r_refresh():
    identity = get_jwt_identity()
    refresh_claims = get_jwt()
    return ok(s_refresh_access(identity, refresh_claims.get("jti")), "Token refreshed successfully.")

@bp.post("/signout")
@jwt_required()
def r_signout():
    uid = get_jwt_identity()
    jti = get_jwt()["jti"]
    user = User.objects(id=uid).first()
    s_signout(user, jti)
    return no_content("User signed out successfully.")

@bp.post("/signout-all")
@jwt_required()
def r_signout_all():
    uid = get_jwt_identity()
    user = User.objects(id=uid).first()
    s_signout_all(user)
    return no_content("All sessions revoked successfully.")

@bp.get("/sessions")
@jwt_required()
def r_sessions():
    uid = get_jwt_identity()
    user = User.objects(id=uid).first()
    return ok(s_list_sessions(user), "User sessions listed successfully.")

@bp.delete("/session/<sid>")
@jwt_required()
def r_revoke_session(sid):
    uid = get_jwt_identity()
    user = User.objects(id=uid).first()
    s_revoke_session(user, sid)
    return no_content("Session revoked successfully.")

@bp.post("/change-password")
@jwt_required()
def r_change_password():
    uid = get_jwt_identity()
    s_change_password(uid, request.get_json() or {})
    return no_content("Password changed successfully.")

@bp.post("/forgot-password")
def r_forgot_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise AppError("Missing email", 400)
    s_forgot_password(email)
    return no_content("Password reset token sent successfully.")

@bp.post("/reset-password")
def r_reset_password():
    data = request.get_json() or {}
    token = data.get("token")
    new_password = data.get("new_password")
    if not token or not new_password:
        raise AppError("Invalid token or new password", 400)
    s_reset_password(token, new_password)
    return no_content("Password reset successfully.")

@bp.post("/send-verify-email")
def r_send_verify_email():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise AppError("Missing email", 400)
    s_send_verify(email)
    return no_content("Verification email sent successfully.")

@bp.post("/verify-email")
def r_verify_email():
    data = request.get_json() or {}
    token = data.get("token")
    if not token:
        raise AppError("Missing token", 400)
    s_verify_email(token)
    return no_content("Email verified successfully.")

@bp.get("/debug/claims")
@jwt_required()
def r_debug_claims():
    return ok(get_jwt(), "Debug claims.")