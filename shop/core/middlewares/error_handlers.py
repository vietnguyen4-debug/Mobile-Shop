from flask import g
from werkzeug.exceptions import NotFound, MethodNotAllowed
from mongoengine.errors import ValidationError as MongoValidationError
from ..responses import fail
from ..exceptions import AppError

def register_error_handlers(app):
    @app.errorhandler(AppError)
    def _app_error(e: AppError):
        return fail(
            e.message,
            code=e.code,
            name=e.name,
            detail=e.detail,
            http_status=e.status
        )

    @app.errorhandler(NotFound)
    def _404(_):
        return fail("Not found", code=404, name="NOT_FOUND")

    @app.errorhandler(MethodNotAllowed)
    def _405(_):
        return fail("Method not allowed", code=405, name="METHOD_NOT_ALLOWED")

    @app.errorhandler(MongoValidationError)
    def _422(e):
        return fail("Validation error", code=422, name="VALIDATION_ERROR", detail={"detail": str(e)})

    @app.errorhandler(Exception)
    def _500(e):
        app.logger.exception("Unhandled error: %s (rid=%s)", e, getattr(g, "request_id", None))
        if app.config.get("ERROR_HTTP_200", False):
            return fail("Internal server error", code=500, name="INTERNAL_ERROR", http_status=200)
        return fail("Internal server error", code=500, name="INTERNAL_ERROR", http_status=500)