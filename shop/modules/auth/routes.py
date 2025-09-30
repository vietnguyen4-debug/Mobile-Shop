from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from datetime import timedelta

from . import bp
from .services import signup, signin
from ...core.responses import ok, created

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