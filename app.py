from dotenv import load_dotenv

# Load environment variables before importing the app to ensure
# SECRET_KEY and JWT_SECRET_KEY are read from .env on startup.
load_dotenv()

from shop import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
