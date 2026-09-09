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
#
# NOTE: --clear is NOT used by default any more, and that is the point.
#
# This script runs on every container start, including every automatic restart
# triggered by a failed healthcheck. `collectstatic --clear` deletes the entire
# staticfiles tree and re-copies it, which is slow and, while it is running,
# means Django admin and DRF pages are being served from a directory that is
# half-empty. Combined with the healthcheck restart loop (see the comment in
# apps/health/deploy_views.py), a brief Redis blip turned into a ~90 second
# outage that repeated.
#
# Without --clear, collectstatic only copies files whose timestamps differ, so a
# restart with no code change is close to instant and never empties the
# directory. Stale files can accumulate across deploys; that is a much smaller
# problem than the one above, and it is what COLLECTSTATIC_CLEAR is for.
#
# Set COLLECTSTATIC_CLEAR=true for a one-off clean rebuild during a deploy:
#     docker compose -f docker-compose.prod.yml run --rm \
#         -e COLLECTSTATIC_CLEAR=true backend python manage.py collectstatic --noinput --clear
#
# Note that staticfiles is a bind mount (/srv/aurora/shared/static), so baking
# collectstatic into the image at build time would be shadowed at runtime. It
# has to happen here or as an explicit deploy step.
if [ "${RUN_COLLECTSTATIC:-false}" = "true" ]; then
  if [ "${COLLECTSTATIC_CLEAR:-false}" = "true" ]; then
    echo "Collecting static files (with --clear)..."
    python manage.py collectstatic --noinput --clear
  else
    echo "Collecting static files (incremental)..."
    python manage.py collectstatic --noinput
  fi
fi

# ── Hand off to compose command: ─────────────────────────────────────────────
# backend      → gunicorn --bind 0.0.0.0:8000 -c config/gunicorn.conf.py config.wsgi:application
# celery_worker → celery -A config worker --loglevel=info
# celery_worker also runs beat, embedded via -B (see docker-compose.prod.yml).
# There is no separate celery_beat container any more: on a 1 GB box a third
# full Django process cost ~160 MB to run a scheduler loop.
echo "Starting application..."
exec "$@"