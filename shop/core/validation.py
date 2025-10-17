from ..core.exceptions import AppError

def require_fields(data, *fields):
    if not isinstance(data, dict):
        raise AppError("Invalid request body: expected JSON object", 400, name="INVALID_JSON_BODY")
    miss = [f for f in fields if data.get(f) in (None, "", [])]
    if miss:
        raise AppError(f"Missing required fields: {', '.join(miss)}", 400, name="MISSING_FIELDS", detail={"fields": miss})
