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

# Create the Flask application instance for the WSGI server to use.
# Do NOT monkey-patch eventlet/gevent here; that must happen inside worker
# processes (see gunicorn_config.py) to avoid patching the master/arbiter.
app = create_app()
