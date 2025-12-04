"""Lightweight ping task for worker health checks."""

from shop.tasks import celery


@celery.task(name="tasks.ping")
def ping():
    """Return a constant string so we can verify the worker is alive."""
    return "pong"


__all__ = ["ping"]
