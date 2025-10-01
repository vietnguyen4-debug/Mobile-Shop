import os
from datetime import timedelta

class DevConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key') or 'you-will-never-guess'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-dev') or 'jwt-you-will-never-guess'
    MONGODB_NAME = os.environ.get("MONGODB_NAME", "mobile_shop")
    MONGODB_HOST = os.environ.get("MONGODB_HOST", "127.0.0.1")
    MONGODB_PORT = int(os.environ.get("MONGODB_PORT", 27017))
    CACHE_TYPE = "SimpleCache"
    JSON_SORT_KEYS = False
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    JWT_ACCESS_TTL_SECONDS = 8*3600
