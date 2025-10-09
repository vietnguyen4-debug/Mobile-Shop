from .request_id import request_id_middleware
from .timing import timing_middleware
from .security_headers import security_headers_middleware
from .cors import cors_middleware
from .logging import logging_middleware
from .error_handlers import register_error_handlers

def register_middlewares(app):
    request_id_middleware(app)
    timing_middleware(app)
    security_headers_middleware(app)
    cors_middleware(app)
    logging_middleware(app)

    register_error_handlers(app)