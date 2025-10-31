import os
from datetime import timedelta

class DevConfig:
    SECRET_KEY = os.environ["SECRET_KEY"]
    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    MONGODB_NAME = os.environ.get("MONGODB_NAME", "mobile_shop")
    MONGODB_HOST = os.environ.get("MONGODB_HOST", "127.0.0.1")
    MONGODB_PORT = int(os.environ.get("MONGODB_PORT", 27017))
    MONGODB_URI = os.environ.get("MONGODB_URI")
    CHECKOUT_PENDING_TTL_SECONDS = int(
        os.environ.get("CHECKOUT_PENDING_TTL_SECONDS", 24 * 60 * 60)
    )
    CACHE_TYPE = "SimpleCache"
    JSON_SORT_KEYS = False
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    JWT_REFRESH_COOKIE_NAME = "refresh_token"
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_ACCESS_TTL_SECONDS = None
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    ERROR_HTTP_200 = True
    CART_SESSION_COOKIE_SECURE = True
    CART_SESSION_COOKIE_SAMESITE = "Lax"

