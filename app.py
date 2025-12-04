import os
import sys
from dotenv import load_dotenv

# Load environment variables before importing the app to ensure
# SECRET_KEY and JWT_SECRET_KEY are read from .env on startup.
load_dotenv()

from shop import create_app

app = create_app()

if __name__ == '__main__':
    import logging
    import subprocess
    import atexit

    logging.basicConfig(level=logging.INFO)
    start_worker = os.getenv("START_CELERY_WITH_APP", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    worker_proc = None
    use_reloader = os.getenv("APP_RELOAD", "true").lower() in ("1", "true", "yes", "on")

    if start_worker:
        # Avoid double-spawning worker when Flask reloader forks.
        if use_reloader:
            use_reloader = False
            logging.info("Disabling reloader because START_CELERY_WITH_APP is enabled.")

        cmd = [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "shop.tasks",
            "worker",
            "--loglevel=info",
        ]
        logging.info("Starting Celery worker: %s", " ".join(cmd))
        worker_proc = subprocess.Popen(cmd)

        def _stop_worker():
            if worker_proc and worker_proc.poll() is None:
                worker_proc.terminate()

        atexit.register(_stop_worker)

    app.run(debug=False, use_reloader=use_reloader)
