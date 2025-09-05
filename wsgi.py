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
# Ensure eventlet monkey-patch runs as early as possible when available.
# Placing the monkey-patch here (the WSGI entrypoint) helps avoid situations
# where blocking OS calls are made inside the eventlet mainloop. This mirrors
# the guidance in the Flask-SocketIO docs: monkey-patch before importing
# networking libraries and before Gunicorn forks workers.
try:
    import eventlet  # type: ignore
    eventlet.monkey_patch()
except Exception:
    # If eventlet isn't installed or monkey-patch fails, continue. Gunicorn
    # worker class should fall back appropriately (but may revert to sync).
    pass

app = create_app()
