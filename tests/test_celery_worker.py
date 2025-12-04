import importlib
import os
import unittest


# Minimal env so create_app/create_celery_app can boot without KeyError.
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("CACHE_REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")


class TestCeleryWorker(unittest.TestCase):
    def setUp(self):
        # Reload to ensure Celery picks up env overrides in this test process.
        self.tasks_module = importlib.reload(importlib.import_module("shop.tasks"))
        self.celery_app = self.tasks_module.create_celery_app()
        # Run tasks eagerly so no external worker/broker is needed.
        self.celery_app.conf.task_always_eager = True
        self.celery_app.conf.task_eager_propagates = True

    def test_task_runs_in_app_context_and_returns_result(self):
        @self.celery_app.task
        def add(a, b):
            from flask import current_app

            # AppContextTask should provide a Flask app context.
            self.assertTrue(current_app)
            return a + b

        result = add.delay(1, 2)
        self.assertTrue(result.successful())
        self.assertEqual(result.get(), 3)

    def test_default_queue_configuration(self):
        self.assertEqual(self.celery_app.conf.task_default_queue, "default")


class TestPingTask(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks_module = importlib.reload(importlib.import_module("shop.tasks"))
        cls.celery_app = cls.tasks_module.celery
        cls.celery_app.conf.task_always_eager = True
        cls.celery_app.conf.task_eager_propagates = True
        importlib.reload(importlib.import_module("shop.tasks.ping"))

    def test_ping_returns_pong(self):
        from shop.tasks.ping import ping

        result = ping.delay()
        self.assertEqual(result.get(), "pong")


if __name__ == "__main__":
    unittest.main()
