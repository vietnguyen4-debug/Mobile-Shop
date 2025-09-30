from functools import wraps
from flask import g
from .responses import error

def require_role(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if g.user.role not in roles:
                return error("Permission denied", status_code=403)
            return func(*args, **kwargs)
        return wrapper
    return decorator()