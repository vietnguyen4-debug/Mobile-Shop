import copy
from typing import Any, Dict, Optional

import awsgi

from app import app as application


HEALTH_PATH = "/api/health"


def _ensure_health_path(event: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a copy of the event that targets the /api/health endpoint."""
    original_event: Dict[str, Any] = event or {}
    normalized_event = copy.deepcopy(original_event)

    normalized_event["path"] = HEALTH_PATH
    normalized_event["rawPath"] = HEALTH_PATH

    request_context = normalized_event.get("requestContext")
    if isinstance(request_context, dict):
        request_context = copy.deepcopy(request_context)
        http_context = request_context.get("http")
        if isinstance(http_context, dict):
            http_context = copy.deepcopy(http_context)
            http_context["path"] = HEALTH_PATH
            request_context["http"] = http_context
        normalized_event["requestContext"] = request_context

    return normalized_event


def handler(event: Optional[Dict[str, Any]], context: Any):
    safe_event: Dict[str, Any] = event or {}
    path = safe_event.get("rawPath") or safe_event.get("path") or ""
    if path in {"", "/"}:
        safe_event = _ensure_health_path(safe_event)
    return awsgi.response(application, safe_event, context)