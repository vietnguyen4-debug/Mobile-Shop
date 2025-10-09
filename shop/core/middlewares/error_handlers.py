from flask import jsonify, g
from werkzeug.exceptions import NotFound, MethodNotAllowed
from mongoengine.errors import ValidationError as MongoValidationError

def _json_error(message, status=400, code=None, extra=None):
    payload = {
        "error": {
            "message": message,
            "code": code or status,
            "request_id": getattr(g, "request_id", None),
        }
    }
    if extra:
        payload["error"].update(extra)
    resp = jsonify(payload)
    resp.status_code = status
    return resp

def register_error_handlers(app):
    try:
        from ..exceptions import AppError
    except Exception:
        class AppError(Exception):  # fallback an toàn khi import lỗi
            def __init__(self, message, status=400, code=None, extra=None):
                super().__init__(message)
                self.message = message
                self.status = status
                self.code = code
                self.extra = extra or {}

    @app.errorhandler(AppError)
    def _handle_app_error(e: "AppError"):
        return _json_error(
            getattr(e, "message", "Bad request"),
            status=getattr(e, "status", 400),
            code=getattr(e, "code", None),
            extra=getattr(e, "extra", None),
        )

    @app.errorhandler(NotFound)
    def _handle_404(e):
        return _json_error("Not found", status=404)

    @app.errorhandler(MethodNotAllowed)
    def _handle_405(e):
        return _json_error("Method not allowed", status=405)

    @app.errorhandler(MongoValidationError)
    def _handle_mongo_validation(e):
        return _json_error("Validation error", status=422, extra={"detail": str(e)})

    @app.errorhandler(Exception)
    def _handle_500(e):
        # log stacktrace vào app.logger
        app.logger.exception("Unhandled error: %s", e)
        return _json_error("Internal server error", status=500)
