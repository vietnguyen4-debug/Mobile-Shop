import os
from datetime import timedelta

class DevConfig:
    _default_celery_broker = os.environ.get(
        "CACHE_REDIS_URL", "redis://127.0.0.1:6379/1"
    )

    SECRET_KEY = os.environ["SECRET_KEY"]
    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    MONGODB_NAME = os.environ.get("MONGODB_NAME", "mobile_shop")
    MONGODB_HOST = os.environ.get("MONGODB_HOST", "127.0.0.1")
    MONGODB_PORT = int(os.environ.get("MONGODB_PORT", 27017))
    MONGODB_URI = os.environ.get("MONGODB_URI")
    CHECKOUT_PENDING_TTL_SECONDS = int(
        os.environ.get("CHECKOUT_PENDING_TTL_SECONDS", 24 * 60 * 60)
    )
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "RedisCache")
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", 300))
    CACHE_REDIS_URL = os.environ["CACHE_REDIS_URL"]
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", _default_celery_broker)
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND", CELERY_BROKER_URL
    )
    CELERY_TASK_DEFAULT_QUEUE = os.environ.get(
        "CELERY_TASK_DEFAULT_QUEUE", "default"
    )
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
