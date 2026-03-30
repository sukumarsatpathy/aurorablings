# Stage 1: Build Dependencies
FROM python:3.11.7-slim-bullseye AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"
ENV HOME=/home/django

# Set work directory
WORKDIR /app

# Install runtime dependencies ONLY
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat \
    curl \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi7 \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create a non-root user
RUN addgroup --system django && \
    adduser --system --group django

# Create directory structure for static and media
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R django:django /app/staticfiles /app/media /app/logs

# Copy project files
COPY --chown=django:django . /app/

# Make entrypoint executable (if they are not already)
RUN chmod +x /app/scripts/entrypoint.sh

# Change to non-root user
USER django

# Run entrypoint.sh
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
