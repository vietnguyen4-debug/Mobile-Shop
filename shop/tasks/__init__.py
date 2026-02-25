from celery import Celery
from dotenv import load_dotenv
# Ensure .env is loaded when the Celery worker starts outside of Flask.
load_dotenv()


def create_celery_app(flask_app=None) -> Celery:
    """
    Create a Celery app bound to the Flask application context so tasks can
    use Flask config, DB connections, etc.
    """
    from shop import create_app

    flask_app = flask_app or create_app()
    broker_url = flask_app.config["CELERY_BROKER_URL"]
    result_backend = flask_app.config.get("CELERY_RESULT_BACKEND", broker_url)

    celery = Celery(
        flask_app.import_name,
        broker=broker_url,
        backend=result_backend,
    )
    celery.conf.update(
        {
            "broker_url": broker_url,
            "result_backend": result_backend,
            "task_default_queue": flask_app.config.get(
                "CELERY_TASK_DEFAULT_QUEUE", "default"
            ),
            "worker_prefetch_multiplier": int(
                flask_app.config.get("CELERY_WORKER_PREFETCH_MULTIPLIER", 1)
            ),
            "task_acks_late": bool(flask_app.config.get("CELERY_TASK_ACKS_LATE", True)),
            "task_reject_on_worker_lost": bool(
                flask_app.config.get("CELERY_TASK_REJECT_ON_WORKER_LOST", True)
            ),
            "task_time_limit": int(flask_app.config.get("CELERY_TASK_TIME_LIMIT", 60)),
            "task_soft_time_limit": int(
                flask_app.config.get("CELERY_TASK_SOFT_TIME_LIMIT", 45)
            ),
        }
    )

    class AppContextTask(celery.Task):
        """Wrap tasks to run inside the Flask app context."""

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return super().__call__(*args, **kwargs)

    celery.Task = AppContextTask

    beat_schedule: dict = {}

    # Configure beat schedule to auto-cancel expired checkouts if enabled.
    interval = int(flask_app.config.get("CANCEL_EXPIRED_CHECKOUTS_INTERVAL_SECONDS", 0))
    if interval > 0:
        beat_schedule["cancel-expired-checkouts"] = {
            "task": "tasks.cancel_expired_checkouts",
            "schedule": interval,  # seconds
        }

    cart_cleanup_interval = int(flask_app.config.get("EXPIRE_GUEST_CARTS_INTERVAL_SECONDS", 0))
    if cart_cleanup_interval > 0:
        beat_schedule["expire-guest-carts"] = {
            "task": "tasks.expire_guest_carts",
            "schedule": cart_cleanup_interval,  # seconds
        }

    vnpay_interval = int(flask_app.config.get("VNPAY_RECONCILE_PENDING_INTERVAL_SECONDS", 0))
    if vnpay_interval > 0:
        beat_schedule["reconcile-pending-vnpay-payments"] = {
            "task": "tasks.reconcile_pending_vnpay_payments",
            "schedule": vnpay_interval,  # seconds
        }

    if beat_schedule:
        celery.conf.beat_schedule = beat_schedule
    return celery


celery = create_celery_app()

# Import built-in tasks so the worker registers them on startup.
try:
    from . import ping  # noqa: F401
    from . import cleanup  # noqa: F401
    from . import vnpay  # noqa: F401
    from . import fulfillment  # noqa: F401
except Exception:
    # Avoid import errors during partial initialization; tasks can still be registered later.
    pass

__all__ = ["celery", "create_celery_app"]
