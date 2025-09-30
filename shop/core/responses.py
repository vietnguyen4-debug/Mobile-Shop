from flask import jsonify

def ok(data, status_code=200):
    return jsonify({"data": data, "error": None}), status_code

def created(data):
    return ok(data, status_code=201)

def no_content():
    return "", 204

def error(message, status_code=400, detail=None):
    return jsonify({
        "data": None,
        "error": {
            "code": status_code,
            "message": message,
            "detail": detail or {}
        }
    }), status_code