from ..core.exceptions import AppError

def require_fields(data: dict, *fields):
    miss = [f for f in fields if not data.get(f)]
    if miss:
        raise AppError(f"Missing fields: {', '.join(miss)}", 400)
