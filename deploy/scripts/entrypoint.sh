#!/usr/bin/env bash
set -euo pipefail

# Create logs dir at runtime with correct permissions
mkdir -p /app/logs

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

# Hand off to whatever command: was passed in compose
# backend  → gunicorn -c config/gunicorn.conf.py config.wsgi:application
# worker   → celery -A config worker --loglevel=info
# beat     → celery -A config beat --loglevel=info
exec "$@"