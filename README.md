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

If you'd like, I can:
- Create a PR branch and push these changes (I can prepare the branch locally and show the diff here).
- Add a simple `Makefile` or `scripts/deploy.sh` to start Gunicorn with the recommended options.

