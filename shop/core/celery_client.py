from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from celery import Celery


@lru_cache(maxsize=1)
def _celery_client() -> Celery:
    broker_url = os.environ.get("CELERY_BROKER_URL") or os.environ.get("CACHE_REDIS_URL")
    if not broker_url:
        raise RuntimeError("CELERY_BROKER_URL (or CACHE_REDIS_URL) must be set")
    backend = os.environ.get("CELERY_RESULT_BACKEND", broker_url)
    return Celery("shop_client", broker=broker_url, backend=backend)


def enqueue_task(
    name: str,
    *,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    countdown: int | None = None,
    queue: str | None = None,
) -> str:
    """
    Enqueue a Celery task by name without importing the app's Celery instance.
    This avoids circular imports from request-handling code.
    """
    client = _celery_client()
    result = client.send_task(
        name,
        args=args or [],
        kwargs=kwargs or {},
        countdown=countdown,
        queue=queue,
    )
    return str(result.id)

