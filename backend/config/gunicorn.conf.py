from __future__ import annotations

import os
from pathlib import Path

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")


def available_cpus() -> int:
    """CPUs this process may actually use — not the machine's core count.

    `multiprocessing.cpu_count()` reads the host's CPU topology. It ignores
    cgroup CPU limits entirely, and on a container-based VPS (LXC/OpenVZ) it
    reports the *physical host's* cores rather than the vCPUs you pay for. A
    2-vCPU slice of a 16-core box therefore sized itself for 16 cores and
    forked 17 workers x 4 threads onto two cores' worth of quota. On a Mac,
    Docker Desktop's VM has a small fixed CPU count, so this never reproduced
    locally -- it only ever went wrong in production.

    Order of preference:
      1. cgroup v2 quota  (/sys/fs/cgroup/cpu.max)
      2. cgroup v1 quota  (cpu.cfs_quota_us / cpu.cfs_period_us)
      3. CPU affinity mask actually scheduled to us
      4. os.cpu_count()
    Always at least 1.
    """
    # cgroup v2
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota != "max":
            return max(1, int(int(quota) / int(period)))
    except Exception:
        pass

    # cgroup v1
    try:
        quota = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
        period = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
        if quota > 0 and period > 0:
            return max(1, int(quota / period))
    except Exception:
        pass

    try:
        return max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        pass

    return max(1, os.cpu_count() or 1)


CPUS = available_cpus()

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
#
# On a 1 vCPU / 1 GB box the binding constraint is RAM, not CPU: each gunicorn
# worker is a full Django process at roughly 180 MB resident, and more workers
# than cores buys nothing on a single core except memory pressure and context
# switching. Set GUNICORN_WORKERS explicitly in the environment for anything
# other than the smallest box -- the formula below is a floor, not a target.
workers = int(os.getenv("GUNICORN_WORKERS", max(1, CPUS)))

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
