def security_headers_middleware(app):
    @app.after_request
    def _set_security_headers(resp):
        h = resp.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "SAMEORIGIN")
        h.setdefault("X-XSS-Protection", "1; mode=block")
        h.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https:; media-src 'self' https:; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'"
        )
        h.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
        return resp
