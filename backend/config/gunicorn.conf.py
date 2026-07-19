from __future__ import annotations

import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")

# Worker count is deliberately lower than the classic (2*cores)+1 formula.
# That formula assumes sync workers with one request each. Now that each worker
# runs multiple threads (below), total concurrency is workers*threads, and each
# of those slots can hold its own persistent Postgres connection because
# settings.base sets CONN_MAX_AGE > 0. (2*cores)+1 workers * 4 threads on a
# 4-core box would reserve 36 connections against Postgres' default
# max_connections of 100 -- survivable, but tight and easy to trip over later.
#
# cores+1 workers * 4 threads keeps concurrency healthy while bounding the
# connection pool. If you raise either value, check:
#     SHOW max_connections;
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() + 1))

# Threaded workers, not sync.
#
# With worker_class="sync" and threads=1, a worker is blocked for the full
# duration of a request. The slowest paths here are I/O-bound -- waiting on
# Postgres, Redis, Stripe, Razorpay, notification providers -- so a sync worker
# spends most of its time idle while holding a request slot. On a 2-core box
# that capped the whole site at 5 concurrent requests.
#
# gthread releases the GIL during I/O waits, so 4 threads per worker raises
# concurrency ~4x on the same hardware.
#
# Not using UvicornWorker: this codebase is sync Django throughout (sync ORM,
# sync views), so an ASGI worker would just push everything through a thread
# pool anyway while adding a failure mode. Revisit if the views go async.
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.getenv("GUNICORN_THREADS", "4"))

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

capture_output = True
preload_app = False
worker_tmp_dir = "/dev/shm"
