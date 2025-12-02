import os
from dotenv import load_dotenv

# Load environment variables before importing the app to ensure
# SECRET_KEY and JWT_SECRET_KEY are read from .env on startup.
load_dotenv()

from shop import create_app

app = create_app()

if __name__ == '__main__':
    import logging

    logging.basicConfig(level=logging.INFO)
    use_reloader = os.getenv("APP_RELOAD", "true").lower() in ("1", "true", "yes", "on")
    app.run(debug=False, use_reloader=use_reloader)
