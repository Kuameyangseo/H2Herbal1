import os

# Do not preload the application into the Gunicorn master process. This
# prevents third-party libraries (eventlet/gevent) from being imported or
# monkey-patched in the master, which can break the mainloop.
preload_app = False

# Reasonable defaults; these can be overridden via environment variables
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', '30'))
workers = int(os.environ.get('GUNICORN_WORKERS', '1'))
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'eventlet')


def post_worker_init(worker):
    """Run inside the worker process after it has been forked/started.

    This is the correct place to apply eventlet/gevent monkey-patching so
    only worker processes (not the master/arbiter) get patched.
    """
    try:
        # Importing and monkey-patching here runs inside the worker process.
        import eventlet  # type: ignore
        eventlet.monkey_patch()
        worker.log.info('Applied eventlet.monkey_patch() in worker')
    except Exception:
        # If eventlet isn't available, do nothing; worker_class may differ.
        worker.log.info('eventlet not available in worker; skipping monkey_patch')
