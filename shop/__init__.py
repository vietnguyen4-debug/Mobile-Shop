from flask import Flask

import config
from .extensions import db, jwt, cors, cache
from .core.exceptions import register_errors
from .modules.auth.models_token import TokenBlocklist
from .modules.auth.routes import bp as auth_bp
from .modules.users.routes import bp as users_bp

def create_app(config_object=config.DevConfig):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app)
    cache.init_app(app)

    register_errors(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)


    @jwt.token_in_blocklist_loader
    def _is_token_revoked(_jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        return TokenBlocklist.objects(jti=jti, revoked=True).first() is not None


    @app.get("/api/health")
    def health():
        return {
            "data": {"status": "ok"},
            "error": None
        }
    return app