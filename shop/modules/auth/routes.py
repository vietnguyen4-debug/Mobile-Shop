from typing import Any

from flask_jwt_extended import (
    jwt_required,
    set_refresh_cookies,
    unset_refresh_cookies
)

from . import bp
from .services import *
from ..users.models import User
from ...core.responses import ok, created, no_content
from ...core.rbac import *

def _extract_refresh_token(payload: Any) -> tuple[Any, str | None]:
    """Split refresh token from payload without mutating the original dict."""

    if not isinstance(payload, dict):
        return payload, None

    refresh_token = payload.get("refresh_token")
    if refresh_token is None:
        return payload, None

    clean_payload = dict(payload)
    clean_payload.pop("refresh_token", None)
    if isinstance(refresh_token, str) and refresh_token:
        return clean_payload, refresh_token

    return clean_payload, None


def _attach_refresh_cookie(response, refresh_token: str | None):
    if isinstance(refresh_token, str) and refresh_token:
        set_refresh_cookies(response, refresh_token)
    return response

@bp.post("/signup")
def r_signup():
    data = request.get_json() or {}
    result, refresh_token = _extract_refresh_token(s_signup(data))
    response = created(result, "User created successfully.")
    return _attach_refresh_cookie(response, refresh_token)

@bp.post("/signin")
def r_signin():
    data = request.get_json() or {}
    result, refresh_token = _extract_refresh_token(s_signin(data))
    response = ok(result, "User signed in successfully.")
    return _attach_refresh_cookie(response, refresh_token)

@bp.post("/refresh")
@jwt_required(refresh=True)
def r_refresh():
    identity = get_jwt_identity()
    refresh_claims = get_jwt()
    result, refresh_token = _extract_refresh_token(
        s_refresh_access(identity, refresh_claims.get("jti"))
    )
    response = ok(result, "Token refreshed successfully.")
    return _attach_refresh_cookie(response, refresh_token)


@bp.post("/signout")
@jwt_required()
def r_signout():
    uid = get_jwt_identity()
    jti = get_jwt()["jti"]
    user = User.objects(id=uid).first()
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        cookie_name = current_app.config.get("JWT_REFRESH_COOKIE_NAME", "refresh_token_cookie")
        refresh_token = request.cookies.get(cookie_name)
    s_signout(
        user,
        jti,
        refresh_token=refresh_token,
        refresh_jti=data.get("refresh_jti"),
        session_id=data.get("session_id"),
    )
    response = no_content("User signed out successfully.")
    unset_refresh_cookies(response)
    return response

@bp.post("/signout-all")
@jwt_required()
def r_signout_all():
    uid = get_jwt_identity()
    user = User.objects(id=uid).first()
    s_signout_all(user)
    response = no_content("All sessions revoked successfully.")
    unset_refresh_cookies(response)
    return response

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