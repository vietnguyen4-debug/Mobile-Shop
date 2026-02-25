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
    CHECKOUT_TTL_RENEW_THRESHOLD_SECONDS = int(
        os.environ.get("CHECKOUT_TTL_RENEW_THRESHOLD_SECONDS", 5 * 60)
    )
    CANCEL_EXPIRED_CHECKOUTS_INTERVAL_SECONDS = int(
        os.environ.get("CANCEL_EXPIRED_CHECKOUTS_INTERVAL_SECONDS", 600)
    )
    VNPAY_RECONCILE_PENDING_INTERVAL_SECONDS = int(
        os.environ.get("VNPAY_RECONCILE_PENDING_INTERVAL_SECONDS", 0)
    )
    VNPAY_RECONCILE_MIN_AGE_SECONDS = int(
        os.environ.get("VNPAY_RECONCILE_MIN_AGE_SECONDS", 300)
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
    CELERY_WORKER_PREFETCH_MULTIPLIER = int(
        os.environ.get("CELERY_WORKER_PREFETCH_MULTIPLIER", 1)
    )
    CELERY_TASK_ACKS_LATE = os.environ.get("CELERY_TASK_ACKS_LATE", "1").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    CELERY_TASK_REJECT_ON_WORKER_LOST = os.environ.get(
        "CELERY_TASK_REJECT_ON_WORKER_LOST", "1"
    ).lower() in ("1", "true", "yes", "on")
    CELERY_TASK_TIME_LIMIT = int(os.environ.get("CELERY_TASK_TIME_LIMIT", 60))
    CELERY_TASK_SOFT_TIME_LIMIT = int(os.environ.get("CELERY_TASK_SOFT_TIME_LIMIT", 45))
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
    CART_SESSION_COOKIE_SECURE = os.environ.get("CART_SESSION_COOKIE_SECURE", "1").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    CART_SESSION_COOKIE_SAMESITE = os.environ.get("CART_SESSION_COOKIE_SAMESITE", "Lax")
    CART_SESSION_COOKIE_MAX_AGE_SECONDS = int(
        os.environ.get("CART_SESSION_COOKIE_MAX_AGE_SECONDS", 30 * 24 * 60 * 60)
    )
    CART_GUEST_IDLE_TTL_SECONDS = int(
        os.environ.get("CART_GUEST_IDLE_TTL_SECONDS", 30 * 24 * 60 * 60)
    )
    CART_GUEST_ABSOLUTE_TTL_SECONDS = int(
        os.environ.get("CART_GUEST_ABSOLUTE_TTL_SECONDS", 90 * 24 * 60 * 60)
    )
    EXPIRE_GUEST_CARTS_INTERVAL_SECONDS = int(
        os.environ.get("EXPIRE_GUEST_CARTS_INTERVAL_SECONDS", 3600)
    )
    CART_SESSION_DEBUG = os.environ.get("CART_SESSION_DEBUG", "0").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
