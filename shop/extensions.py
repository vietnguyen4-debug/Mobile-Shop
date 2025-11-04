from urllib.parse import urlparse

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

db = _MongoEngineWrapper()
jwt = JWTManager()
cors = CORS()
cache = Cache()
