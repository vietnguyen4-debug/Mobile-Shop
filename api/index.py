import copy
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import awsgi

from app import app as application


IGNORED_PATHS = {"/favicon.ico", "/favicon.png"}
FORWARDED_PATH_HEADERS = (
    "x-forwarded-uri",
    "x-forwarded-path",
    "x-forwarded-url",
    "x-original-uri",
    "x-original-url",
    "x-rewrite-url",
    "x-vercel-original-pathname",
)


def _clone_event_with_path(event: Optional[Dict[str, Any]], path: str) -> Dict[str, Any]:
    """Return a copy of the event with the request path replaced."""
    original_event: Dict[str, Any] = event or {}
    normalized_event = copy.deepcopy(original_event)
    normalized_event["path"] = path
    normalized_event["rawPath"] = path

    request_context = normalized_event.get("requestContext")
    if isinstance(request_context, dict):
        request_context = copy.deepcopy(request_context)
        http_context = request_context.get("http")
        if isinstance(http_context, dict):
            http_context = copy.deepcopy(http_context)
            http_context["path"] = path
            request_context["http"] = http_context
        normalized_event["requestContext"] = request_context

    return normalized_event


def _extract_forwarded_path(event: Optional[Dict[str, Any]]) -> str:
    """Extract the original request path from common forwarding headers."""
    if not isinstance(event, dict):
        return ""

    headers = event.get("headers")
    if not isinstance(headers, dict):
        return ""

    normalized_headers: Dict[str, str] = {}
    for key, value in headers.items():
        if isinstance(key, str) and isinstance(value, str):
            normalized_headers[key.lower()] = value

    for header in FORWARDED_PATH_HEADERS:
        raw_value = normalized_headers.get(header)
        if not raw_value:
            continue

        parsed = urlsplit(raw_value)
        candidate = parsed.path or raw_value.split("?", 1)[0]
        if candidate:
            return candidate

    return ""


def handler(event: Optional[Dict[str, Any]], context: Any):
    forwarded_path = _extract_forwarded_path(event)
    if forwarded_path:
        safe_event = _clone_event_with_path(event, forwarded_path)
    else:
        safe_event = copy.deepcopy(event or {})

    path = forwarded_path or safe_event.get("rawPath") or safe_event.get("path") or ""
    if path in IGNORED_PATHS:
        return {
            "statusCode": 204,
            "body": "",
            "headers": {"cache-control": "no-store"},
        }

    if not path:
        safe_event = _clone_event_with_path(safe_event, "/")

    return awsgi.response(application, safe_event, context)