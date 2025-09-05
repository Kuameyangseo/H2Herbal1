#!/bin/sh
# Start Gunicorn with eventlet worker for Socket.IO
# This script ensures the recommended flags are always used.

PORT=${PORT:-8000}
WORKERS=${GUNICORN_WORKERS:-1}
TIMEOUT=${GUNICORN_TIMEOUT:-300}
GRACEFUL_TIMEOUT=${GUNICORN_GRACEFUL_TIMEOUT:-30}

# If multiple workers are requested but no Redis message queue is configured,
# Socket.IO engine sessions won't be shared between workers which commonly
# leads to "Invalid session" errors and broken websocket/polling fallbacks.
# In that case force a single worker and log a clear notice.
if [ "${WORKERS}" -gt 1 ] && [ -z "${REDIS_URL}" ] && [ -z "${REDIS_URL}" ]; then
	echo "WARNING: GUNICORN_WORKERS=${WORKERS} requested but REDIS_URL is not set."
	echo "Socket.IO requires a message queue (Redis) when running multiple workers."
	echo "Falling back to WORKERS=1 to avoid invalid session errors."
	WORKERS=1
fi

exec gunicorn -k eventlet -w ${WORKERS} -b 0.0.0.0:${PORT} wsgi:app --timeout ${TIMEOUT} --graceful-timeout ${GRACEFUL_TIMEOUT} -c gunicorn_config.py
