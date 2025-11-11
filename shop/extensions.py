from urllib.parse import urlparse

import redis
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_caching import Cache
from mongoengine import connect

class _MongoEngineWrapper:
    def __init__(self):
        self._inited = False

    def init_app(self, app):
        if not self._inited:
            mongodb_uri = app.config.get("MONGODB_URI")

            if mongodb_uri:
                db_name = app.config.get("MONGODB_NAME")

                if db_name:
                    parsed = urlparse(mongodb_uri)

                    if not parsed.path or parsed.path == "/":
                        connect(db=db_name, host=mongodb_uri)
                        self._inited = True
                        return
                connect(host=mongodb_uri)
            else:
                connect(
                    db=app.config["MONGODB_NAME"],
                    host=app.config["MONGODB_HOST"],
                    port=app.config["MONGODB_PORT"],
                )
            self._inited = True

class _CacheWrapper(Cache):
    def __init__(self):
        super().__init__()
        self._inited = False
        self.client = None

    def init_app(self, app, config=None):
        if not self._inited:
            redis_url = app.config.get("CACHE_REDIS_URL")

            if not redis_url:
                raise RuntimeError(
                    "CACHE_REDIS_URL must be configured before initializing cache"
                )

            self.client = redis.from_url(redis_url, decode_responses=True)
            app.extensions["redis_client"] = self.client

            super().init_app(app, config=config)
            self._inited = True

db = _MongoEngineWrapper()
jwt = JWTManager()
cors = CORS()
cache = _CacheWrapper()
