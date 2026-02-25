from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import redis


def _redis_client() -> redis.Redis:
    url = os.environ.get("CACHE_REDIS_URL") or os.environ.get("CELERY_BROKER_URL")
    if not url:
        raise RuntimeError("CACHE_REDIS_URL (or CELERY_BROKER_URL) must be set")
    return redis.Redis.from_url(url, decode_responses=True)


@contextmanager
def redis_lock(key: str, *, ttl_seconds: int = 60) -> Iterator[bool]:
    """
    Best-effort distributed lock. Yields True if acquired; otherwise False.
    """
    client = _redis_client()
    acquired = bool(client.set(key, "1", nx=True, ex=int(ttl_seconds)))
    try:
        yield acquired
    finally:
        if acquired:
            try:
                client.delete(key)
            except Exception:
                pass

