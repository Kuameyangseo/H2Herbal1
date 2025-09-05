"""WSGI entrypoint for Gunicorn / hosting platforms.

This exposes a top-level `app` WSGI callable so you can run:
    gunicorn wsgi:app

It intentionally avoids the name collision between the top-level file `app.py`
and the `app` package directory.
"""
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

from app import create_app

# Create the Flask application instance for the WSGI server to use
app = create_app()
