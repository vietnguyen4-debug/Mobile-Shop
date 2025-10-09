import uuid
from flask import g, request

_HEADER = "X-Request-ID"
_FORWARD_KEYS = ("X-REQUEST-ID", "X-CORRELATION-ID", "X-AMZN-TRACE-ID")

def request_id_middleware(app):
    @app.before_request
    def _attach_request_id():
        rid = None
        for k in _FORWARD_KEYS:
            v = request.headers.get(k)
            if v:
                rid = v.strip()
                break
        if not rid:
            rid = uuid.uuid4().hex
        g.request_id = rid

    @app.after_request
    def _propagate_request_id(resp):
        rid = getattr(g, "request_id", None)
        if rid:
            resp.headers[_HEADER] = rid
        return resp