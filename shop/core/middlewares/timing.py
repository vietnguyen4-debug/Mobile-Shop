import time
from flask import g

def timing_middleware(app):
    @app.before_request
    def _start_timer():
        g._t0 = time.perf_counter()

    @app.after_request
    def _add_timing_header(resp):
        t0 = getattr(g, "_t0", None)
        if t0 is not None:
            ms = (time.perf_counter() - t0) * 1000.0
            resp.headers["X-Response-Time"] = f"{ms:.1f}ms"
        return resp
