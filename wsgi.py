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
import os
import sys

# Create the Flask application instance for the WSGI server to use.
# Do NOT monkey-patch eventlet/gevent here; that must happen inside worker
# processes (see gunicorn_config.py) to avoid patching the master/arbiter.
app = create_app()

# Guard: detect if Gunicorn was started with a synchronous worker and warn/exit.
# This check runs in the master process at import time. It only attempts to
# detect a common misconfiguration where the started command omitted ``-k eventlet``
# and used the sync worker which will block on websocket reads.
if 'gunicorn' in os.path.basename(sys.argv[0]).lower() or any('gunicorn' in a for a in sys.argv):
    # If GUNICORN_WORKER_CLASS env or CLI option exists, prefer that. Otherwise
    # attempt to see if the environment explicitly set a worker class.
    worker_class = os.environ.get('GUNICORN_WORKER_CLASS') or os.environ.get('WORKER_CLASS')
    # When using the wrapper script, the command should still use eventlet.
    if worker_class and 'eventlet' not in worker_class:
        sys.stderr.write('ERROR: Gunicorn worker class appears to be "{}"; Socket.IO requires an async worker such as eventlet or gevent.\n'.format(worker_class))
        sys.exit(1)

