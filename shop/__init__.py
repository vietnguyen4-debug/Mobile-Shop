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
from .modules.payment.routes import bp_admin as payment_admin_bp
from .modules.shipment.routes import bp as shipment_bp
from .modules.shipment.routes import bp_admin as shipment_admin_bp
from .modules.checkout.routes import bp as checkout_bp

def create_app(config_object=config.DevConfig):
    app = Flask(__name__)
    app.config.from_object(config_object)

    if hasattr(app, "json"):
        app.json.sort_keys = False

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
    app.register_blueprint(payment_admin_bp)
    app.register_blueprint(shipment_bp)
    app.register_blueprint(shipment_admin_bp)
    app.register_blueprint(checkout_bp)

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

    @app.get("/")
    def root():
        return health()

    _warmup_backends(app)
    return app


def _warmup_backends(app: Flask) -> None:
    """
    Establish initial connections to MongoDB/Redis so the first HTTP request
    doesn't pay the TLS handshake/init penalty.
    """
    if not app.config.get("ENABLE_STARTUP_WARMUP", True):
        return

    try:
        with app.app_context():
            _warmup_mongo_models()
            _warmup_redis()
    except Exception as exc:
        logger = getattr(app, "logger", None)
        if logger:
            logger.warning("Startup warm-up skipped: %s", exc)


def _warmup_mongo_models() -> None:
    try:
        from .modules.catalogs.models import (
            Category,
            SubCategory,
            Product,
            ProductKeyword,
        )
        from .modules.users.models import User
        from .modules.cart.models import Cart
        from .modules.checkout.models import Checkout
        from .modules.shipment.models import Shipment, ShipmentAddress
        from .modules.payment.models import Payment
        from .modules.auth.models_recovery import PasswordReset, EmailVerification
        from .modules.auth.models_session import DeviceSession

        models = [
            Category,
            SubCategory,
            Product,
            ProductKeyword,
            User,
            Cart,
            Checkout,
            Shipment,
            ShipmentAddress,
            Payment,
            PasswordReset,
            EmailVerification,
            DeviceSession,
            TokenBlocklist,
        ]
        for model in models:
            try:
                model.objects.first()
            except Exception:
                continue

        from .modules.catalogs.service_helpers import ensure_product_ranks_initialized

        ensure_product_ranks_initialized()
    except Exception:
        raise


def _warmup_redis() -> None:
    redis_client = getattr(cache, "client", None)
    if redis_client:
        redis_client.ping()

