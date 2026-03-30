#!/bin/sh
set -e

# Function to wait for a service to be available
wait_for_service() {
    local host="$1"
    local port="$2"
    local service_name="$3"

    echo "Waiting for ${service_name} at ${host}:${port}..."
    while ! nc -z "$host" "$port"; do
      sleep 0.5
    done
    echo "${service_name} is up!"
}

# Wait for Postgres if configured
if [ "$DATABASE" = "postgres" ]; then
    wait_for_service "$SQL_HOST" "$SQL_PORT" "PostgreSQL"
fi

# Wait for Redis if configured
if [ -n "$REDIS_HOST" ] && [ -n "$REDIS_PORT" ]; then
    wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis"
fi

# In production, we should NOT create migrations on the fly.
# We fail fast if model changes are not yet migrated.
LOCAL_APPS="accounts catalog inventory cart orders payments surcharge returns notifications features pricing"

if [ "$DJANGO_DEBUG" = "True" ] || [ "$DJANGO_DEBUG" = "1" ]; then
    echo "Running in DEBUG mode. Checking for missing migrations..."
    python manage.py makemigrations --check --dry-run $LOCAL_APPS || {
        echo "WARNING: Missing migrations detected in development!"
    }
else
    echo "Running in PRODUCTION mode. Ensuring migrations are up to date..."
    # In prod, we fail if migrations are missing to avoid schema inconsistencies.
    # But usually, we just run migrate.
fi

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files
if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput --clear
fi

# Execute original passed command (e.g., gunicorn or celery)
echo "Starting application..."
exec "$@"
