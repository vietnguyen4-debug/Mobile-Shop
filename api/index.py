from typing import Callable, Iterable
from urllib.parse import urlsplit

from werkzeug.wrappers import Response

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


class _PathNormalizationMiddleware:
    """Normalize forwarded paths before they reach the Flask app."""

    def __init__(self, wsgi_app: Callable[[dict, Callable], Iterable[bytes]]):
        self._wsgi_app = wsgi_app

    def __call__(self, environ: dict, start_response: Callable):
        forwarded_path = _extract_forwarded_path(environ)

        if forwarded_path:
            environ = dict(environ)
            environ["PATH_INFO"] = forwarded_path
            environ["RAW_PATH_INFO"] = forwarded_path

        path = environ.get("PATH_INFO", "") or ""

        if not path:
            environ = dict(environ)
            environ["PATH_INFO"] = "/"
            environ["RAW_PATH_INFO"] = "/"
            path = "/"

        if path in IGNORED_PATHS:
            response = Response("", status=204)
            response.headers["cache-control"] = "no-store"
            return response(environ, start_response)

        return self._wsgi_app(environ, start_response)


def _extract_forwarded_path(environ: dict) -> str:
    headers = {}
    for key, value in environ.items():
        if not key.startswith("HTTP_"):
            continue
        if not isinstance(value, str):
            continue
        normalized_key = key[5:].lower().replace("_", "-")
        headers[normalized_key] = value

    for header in FORWARDED_PATH_HEADERS:
        raw_value = headers.get(header)
        if not raw_value:
            continue

        parsed = urlsplit(raw_value)
        candidate = parsed.path or raw_value.split("?", 1)[0]
        if candidate:
            return candidate

    return ""


application.wsgi_app = _PathNormalizationMiddleware(application.wsgi_app)

# Expose the Flask application as "app" so the Vercel runtime can pick it up
app = application