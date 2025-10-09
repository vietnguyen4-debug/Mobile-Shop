# core/middlewares/logging.py
import json, time
from flask import request, g
from flask_jwt_extended import get_jwt_identity

def _safe_str(v):
    try:
        return str(v) if v is not None else None
    except Exception:
        return None

def logging_middleware(app):
    def _log(line: dict):
        try:
            app.logger.info(json.dumps(line, ensure_ascii=False))
        except Exception:
            pass

    @app.after_request
    def _access_log(resp):
        try:
            uid = None
            try:
                uid = get_jwt_identity()
            except Exception:
                pass

            line = {
                "ts": int(time.time()),
                "rid": getattr(g, "request_id", None),
                "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
                "method": request.method,
                "path": request.full_path.rstrip("?") if request else None,
                "status": resp.status_code,
                "len": resp.calculate_content_length(),
                "ua": request.user_agent.string if request and request.user_agent else None,
                "uid": _safe_str(uid),
            }
            _log(line)
        except Exception:
            pass
        return resp
