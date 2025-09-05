H2Herbal — Deployment Notes

This repository contains a Flask-based e-commerce app. The following notes are minimal, safe changes and recommendations for running this app in production.

Quick changes applied in this branch/PR
- DEBUG is disabled by default. Use the environment variable `FLASK_DEBUG=1` only for local development.
- SocketIO now prefers `eventlet` (or `gevent`) when available and supports a Redis message queue via `REDIS_URL`.
- `eventlet` and `redis` were added to `requirements.txt` for production readiness.

Recommended production checklist
1. Use a production database (Postgres/MySQL) instead of SQLite. Set `DATABASE_URL` accordingly.
2. Run the app behind a reverse proxy (nginx) to serve static files and handle TLS.
3. Use Gunicorn with the eventlet worker for SocketIO:

   Example (single host, eventlet):

   gunicorn -k eventlet -w 1 -b 0.0.0.0:8000 wsgi:app

   For multiple workers and SocketIO, use a Redis message queue and set `REDIS_URL`:

   REDIS_URL=redis://localhost:6379/0 \n   gunicorn -k eventlet -w 4 -b 0.0.0.0:8000 wsgi:app

4. Add a systemd unit (example provided in `deploy/gunicorn.service`) and ensure your service sets environment variables securely.
5. Serve static files (`/static`) via nginx or a CDN.
6. Add caching (Redis) for sessions or query caching where appropriate.
7. Profile slow endpoints and add DB indexes or eager-loading to prevent N+1 queries.

Quick diagnostics
- Ensure `FLASK_ENV` is not `development` and `FLASK_DEBUG` unset or `0`.
- Check `app.logger` at startup to confirm SocketIO `async_mode` and `message_queue` state.
- Temporarily enable `SQLALCHEMY_ECHO` to inspect slow queries.

Troubleshooting Socket.IO "WORKER TIMEOUT" and "Invalid session" errors
-----------------------------------------------------------------------

If you see logs like "WORKER TIMEOUT (pid:...)" followed by "Invalid session <sid>", it's usually because the default synchronous Gunicorn worker is blocking on websocket/frame I/O. Typical fixes:

- Run Gunicorn with an async worker that supports WebSockets (eventlet or gevent). Example: the repository includes a `Procfile` which starts Gunicorn with the eventlet worker and a higher timeout to reduce spurious worker restarts:

   web: gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT wsgi:app --timeout 120 --graceful-timeout 30

- If you're running multiple Gunicorn workers, configure a Redis message queue and set `REDIS_URL` so SocketIO can scale across workers (the example command for 4 workers shown above requires Redis).
- Ensure `eventlet` is installed (it's already listed in `requirements.txt`).
- Increase `--timeout` to avoid Gunicorn thinking workers are stuck when the websocket driver is doing long blocking reads.
- For debugging, enable Engine.IO logging via the Flask app: set `engineio_logger=True` in `socketio.init_app(...)` (already set in code) and inspect logs for "Invalid session" traces.

If you'd like, I can open a PR that additionally adds a `scripts/deploy.sh`, a `Makefile`, and a short systemd drop-in to show the recommended environment variable setup.

If you'd like, I can:
- Create a PR branch and push these changes (I can prepare the branch locally and show the diff here).
- Add a simple `Makefile` or `scripts/deploy.sh` to start Gunicorn with the recommended options.

