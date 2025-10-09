from flask import request
from ..responses import ok

def cors_middleware(app):
    allow_origins = app.config.get("CORS_ALLOW_ORIGINS", "*")
    allow_methods = app.config.get("CORS_ALLOW_METHODS", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
    allow_headers = app.config.get("CORS_ALLOW_HEADERS", "Content-Type, Authorization")
    allow_credentials = app.config.get("CORS_ALLOW_CREDENTIALS", "true")
    max_age = app.config.get("CORS_MAX_AGE", "3600")

    @app.after_request
    def _add_cors(resp):
        origin = request.headers.get("Origin") or allow_origins
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = allow_methods
        resp.headers["Access-Control-Allow-Headers"] = allow_headers
        resp.headers["Access-Control-Allow-Credentials"] = allow_credentials
        resp.headers["Access-Control-Max-Age"] = max_age
        return resp

    @app.route("/__preflight__", methods=["OPTIONS"])
    def _preflight():
        return ok({"preflight": True})
