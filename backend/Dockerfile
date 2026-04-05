# Stage 1: Build Dependencies
FROM python:3.11.7-slim-bullseye AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies with retry logic for flaky mirrors
RUN apt-get update && \
    apt-get install -y --no-install-recommends --fix-missing \
        build-essential \
        libpq-dev \
        netcat \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-dejavu-core \
    || (apt-get update && apt-get install -y --no-install-recommends --fix-missing \
        build-essential \
        libpq-dev \
        netcat \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-dejavu-core) \
    && rm -rf /var/lib/apt/lists/*

# Create and use a virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install python dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final Production Image
FROM python:3.11.7-slim-bullseye AS runner

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"
ENV HOME=/home/django

WORKDIR /app

# Install runtime dependencies with retry logic
RUN apt-get update && \
    apt-get install -y --no-install-recommends --fix-missing \
        libpq5 \
        netcat \
        curl \
        libcairo2 \
        libpango-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi7 \
        shared-mime-info \
        fonts-dejavu-core \
    || (apt-get update && apt-get install -y --no-install-recommends --fix-missing \
        libpq5 \
        netcat \
        curl \
        libcairo2 \
        libpango-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi7 \
        shared-mime-info \
        fonts-dejavu-core) \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create a non-root user
RUN addgroup --system django && \
    adduser --system --group django

# Create directory structure
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R django:django /app/staticfiles /app/media /app/logs

# Copy project files
COPY --chown=django:django . /app/

# Make entrypoint executable
RUN chmod +x /app/scripts/entrypoint.sh

USER django

ENTRYPOINT ["/app/scripts/entrypoint.sh"]