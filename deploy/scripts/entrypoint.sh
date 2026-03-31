#!/usr/bin/env bash
set -euo pipefail

# ✅ Create logs dir at runtime with correct permissions
mkdir -p /app/logs

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn -c config/gunicorn.conf.py config.wsgi:application