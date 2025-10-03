from functools import wraps
from ..core.exceptions import AppError
from flask_jwt_extended import get_jwt_identity, get_jwt

ROLES = ["admin", "user"]

def _current_role() -> str:
    return get_jwt().get("role", "user")

def is_admin():
    return _current_role() == "admin"

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_admin() and _current_role() not in roles:
                raise AppError("Permission denied", 403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def self_or_admin(param: str):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            uid = str(get_jwt_identity())
            target = str(kwargs.get(param))
            if uid == target or is_admin():
                return f(*args, **kwargs)
            raise AppError("Permission denied", 403)
        return decorated_function
    return decorator


