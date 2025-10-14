from flask import jsonify, g


def _envelope(data=None, *, message="", error=None, status=200):
    body = {
        "data": data if error is None else None,
        "error": error,
        "message": message or ("OK" if error is None else ""),
        "request_id": getattr(g, "request_id", None),
    }
    resp = jsonify(body)
    resp.status_code = status
    return resp

def ok(data = None, message = "OK", status_code = 200):
    return _envelope(data, message=message, status=status_code)

def created(data = None, message = "Created", status_code = 201):
    return _envelope(data, message=message, status=status_code)


def no_content(message = "No Content"):
    return _envelope(None, message=message, status=204)

def fail(message, *, code=400, name=None, detail=None, http_status=None):
    err = {"code": int(code), "name": name, "detail": detail or {}}
    return _envelope(None, message=message, error=err, status=http_status or code)