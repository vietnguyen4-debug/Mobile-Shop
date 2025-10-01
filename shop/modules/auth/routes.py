from flask import request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, get_jwt
from datetime import timedelta

from . import bp
from .services import signup, signin
from ..users.models import User
from ...core.exceptions import AppError
from ...core.responses import ok, created, no_content


@bp.post("/signup")
def signup():
    return created(signup(request.get_json() or {}))

@bp.post("/signin")
def signin():
    return ok(signin(request.get_json() or {}))

@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token_expires = timedelta(days=1)
    return {
        "access_token": create_access_token(
            identity=identity, expires_delta=access_token_expires
        )
    }

@bp.post("/signout")
@jwt_required()
def signout():
    uid = get_jwt_identity()
    jti = get_jwt()["jti"]
    user = User.objects(id=uid).first()
    signout(user, jti, ttl_seconds=current_app.config.get("JWT_ACCESS_TTL_SECONDS", 8*3600))
    return no_content()

@bp.post("/signout-all")
def signout_all():
    uid = get_jwt_identity()
    user = User.objects(id=uid).first()
    signout_all(user)
    return no_content()

@bp.get("/session")
def session():
    uid = get_jwt_identity()
    user = User.objects(id=uid).first()
    return ok(session(user))

@bp.delete("/session/<sid>")
@jwt_required()
def revoke_session(sid):
    uid = get_jwt_identity()
    user = User.objects(id=uid).first()
    revoke_session(user, sid)
    return no_content()

@bp.post("/change-password")
@jwt_required()
def change_password():
    uid = get_jwt_identity()
    change_password(uid, request.get_json() or {})
    return no_content()

@bp.post("/forgot-password")
def forgot_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise AppError("Invalid email", 400)
    forgot_password(email)
    return no_content()

@bp.post("/reset-password")
def reset_password():
    data = request.get_json() or {}
    token = data.get("token")
    new_password = data.get("new_password")
    if not token or not new_password:
        raise AppError("Invalid token or new password", 400)
    reset_password(token, new_password)
    return no_content()

@bp.post("/send-verify-email")
def send_verify_email():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise AppError("Invalid email", 400)
    send_verify_email(email)
    return no_content()

@bp.post("/verify-email")
def verify_email():
    data = request.get_json() or {}
    token = data.get("token")
    if not token:
        raise AppError("Invalid token", 400)
    verify_email(token)
    return no_content()
