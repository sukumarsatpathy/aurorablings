#!/usr/bin/env bash
set -euo pipefail

# Create logs dir at runtime with correct permissions
mkdir -p /app/logs

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL at ${SQL_HOST}:${SQL_PORT}..."
until nc -z "${SQL_HOST}" "${SQL_PORT}"; do
  sleep 1
done
echo "PostgreSQL is up!"

# Wait for Redis to be ready
echo "Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
until nc -z "${REDIS_HOST}" "${REDIS_PORT}"; do
  sleep 1
done
echo "Redis is up!"

# Only the backend service runs migrate + collectstatic.
# celery_worker and celery_beat skip this block entirely.
if [[ "${RUN_MIGRATIONS:-false}" == "true" ]]; then
  echo "Running in PRODUCTION mode. Ensuring migrations are up to date..."

  echo "Applying database migrations..."
  python manage.py migrate --noinput

  echo "Collecting static files..."
  python manage.py collectstatic --noinput

  echo "Setup complete. Handing off to application server..."
fi

echo "Starting application..."

# Hand off to whatever command: was passed in compose
# backend       → gunicorn --bind 0.0.0.0:8000 -c config/gunicorn.conf.py config.wsgi:application
# celery_worker → celery -A config worker --loglevel=info
# celery_beat   → celery -A config beat --loglevel=info
exec "$@"