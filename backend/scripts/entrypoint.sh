#!/bin/sh
set -e

# ── Wait for dependencies ─────────────────────────────────────────────────────
wait_for_service() {
  local host="$1"
  local port="$2"
  local name="$3"
  echo "Waiting for ${name} at ${host}:${port}..."
  while ! nc -z "$host" "$port"; do
    sleep 0.5
  done
  echo "${name} is up!"
}

if [ "$DATABASE" = "postgres" ]; then
  wait_for_service "$SQL_HOST" "$SQL_PORT" "PostgreSQL"
fi

if [ -n "${REDIS_HOST:-}" ] && [ -n "${REDIS_PORT:-}" ]; then
  wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis"
fi

# ── Migrations — only on backend, never on celery_worker or celery_beat ───────
# Set RUN_MIGRATIONS=true only in the backend service in docker-compose.prod.yml
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "Running in PRODUCTION mode. Ensuring migrations are up to date..."
  echo "Applying database migrations..."
  python manage.py migrate --noinput
fi

# ── Static files — only on backend ───────────────────────────────────────────
# Set RUN_COLLECTSTATIC=true only in the backend service in docker-compose.prod.yml
if [ "${RUN_COLLECTSTATIC:-false}" = "true" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput --clear
fi

# ── Hand off to compose command: ─────────────────────────────────────────────
# backend      → gunicorn --bind 0.0.0.0:8000 -c config/gunicorn.conf.py config.wsgi:application
# celery_worker → celery -A config worker --loglevel=info
# celery_beat   → celery -A config beat --loglevel=info --pidfile= --schedule=/app/logs/celerybeat-schedule
echo "Starting application..."
exec "$@"