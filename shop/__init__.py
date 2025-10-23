from flask import Flask

import config
from .extensions import db, jwt, cors, cache
from .core.middlewares import register_middlewares
from .modules.auth.models_token import TokenBlocklist
from .modules.auth.routes import bp as auth_bp
from .modules.users.routes import bp as users_bp
from .modules.catalogs.routes import bp as catalogs_bp
from .modules.catalogs.routes import bp_admin as catalogs_admin_bp
from .modules.cart.routes import bp as cart_bp
from .modules.payment.routes import bp as payment_bp

def create_app(config_object=config.DevConfig):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, supports_credentials=True)
    cache.init_app(app)


    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(catalogs_bp)
    app.register_blueprint(catalogs_admin_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(payment_bp)

    register_middlewares(app)


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