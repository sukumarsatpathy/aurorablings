from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

import psutil
import redis
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError


class ServerHealthService:
    SOURCE = "server"

    def __init__(
        self,
        db_alias: str = "default",
        redis_url: str | None = None,
        redis_timeout_seconds: float = 1.0,
        disk_path: str | None = None,
    ) -> None:
        self.db_alias = db_alias
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_timeout_seconds = redis_timeout_seconds
        self.disk_path = disk_path or self._default_disk_path()

    def run(self) -> list[dict[str, Any]]:
        return [
            self.check_cpu_usage(),
            self.check_memory_usage(),
            self.check_disk_usage(),
            self.check_database_connectivity(),
            self.check_redis_connectivity(),
        ]

    def check_cpu_usage(self) -> dict[str, Any]:
        started = perf_counter()
        usage_percent = psutil.cpu_percent(interval=0.1)
        response_time_ms = self._elapsed_ms(started)

        if usage_percent > 90:
            status = "degraded"
            message = f"CPU usage is high at {usage_percent:.1f}%."
        elif usage_percent > 75:
            status = "warning"
            message = f"CPU usage is elevated at {usage_percent:.1f}%."
        else:
            status = "healthy"
            message = f"CPU usage is normal at {usage_percent:.1f}%."

        return self._result(
            component="cpu",
            status=status,
            message=message,
            response_time_ms=response_time_ms,
            metadata={"usage_percent": usage_percent},
        )

    def check_memory_usage(self) -> dict[str, Any]:
        started = perf_counter()
        usage_percent = psutil.virtual_memory().percent
        response_time_ms = self._elapsed_ms(started)

        if usage_percent > 95:
            status = "degraded"
            message = f"Memory usage is high at {usage_percent:.1f}%."
        elif usage_percent > 85:
            status = "warning"
            message = f"Memory usage is elevated at {usage_percent:.1f}%."
        else:
            status = "healthy"
            message = f"Memory usage is normal at {usage_percent:.1f}%."

        return self._result(
            component="memory",
            status=status,
            message=message,
            response_time_ms=response_time_ms,
            metadata={"usage_percent": usage_percent},
        )

    def check_disk_usage(self) -> dict[str, Any]:
        started = perf_counter()
        usage_percent = psutil.disk_usage(self.disk_path).percent
        response_time_ms = self._elapsed_ms(started)

        if usage_percent > 92:
            status = "down"
            message = f"Disk usage is critical at {usage_percent:.1f}%."
        elif usage_percent > 80:
            status = "warning"
            message = f"Disk usage is elevated at {usage_percent:.1f}%."
        else:
            status = "healthy"
            message = f"Disk usage is normal at {usage_percent:.1f}%."

        return self._result(
            component="disk",
            status=status,
            message=message,
            response_time_ms=response_time_ms,
            metadata={"usage_percent": usage_percent, "path": self.disk_path},
        )

    def check_database_connectivity(self) -> dict[str, Any]:
        started = perf_counter()
        try:
            connection = connections[self.db_alias]
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            return self._result(
                component="database",
                status="healthy",
                message="Database connectivity check passed.",
                response_time_ms=self._elapsed_ms(started),
                metadata={"db_alias": self.db_alias},
            )
        except OperationalError as exc:
            return self._result(
                component="database",
                status="down",
                message=f"Database connectivity check failed: {exc}",
                response_time_ms=self._elapsed_ms(started),
                metadata={"db_alias": self.db_alias},
            )
        except Exception as exc:  # pragma: no cover
            return self._result(
                component="database",
                status="down",
                message=f"Database connectivity check failed: {exc}",
                response_time_ms=self._elapsed_ms(started),
                metadata={"db_alias": self.db_alias},
            )

    def check_redis_connectivity(self) -> dict[str, Any]:
        started = perf_counter()
        try:
            client = redis.Redis.from_url(
                self.redis_url,
                socket_connect_timeout=self.redis_timeout_seconds,
                socket_timeout=self.redis_timeout_seconds,
            )
            client.ping()

            return self._result(
                component="redis",
                status="healthy",
                message="Redis connectivity check passed.",
                response_time_ms=self._elapsed_ms(started),
                metadata={"redis_url": self.redis_url},
            )
        except redis.RedisError as exc:
            return self._result(
                component="redis",
                status="down",
                message=f"Redis connectivity check failed: {exc}",
                response_time_ms=self._elapsed_ms(started),
                metadata={"redis_url": self.redis_url},
            )
        except Exception as exc:  # pragma: no cover
            return self._result(
                component="redis",
                status="down",
                message=f"Redis connectivity check failed: {exc}",
                response_time_ms=self._elapsed_ms(started),
                metadata={"redis_url": self.redis_url},
            )

    def _default_disk_path(self) -> str:
        base_dir = getattr(settings, "BASE_DIR", None)
        if base_dir:
            anchor = Path(str(base_dir)).anchor
            if anchor:
                return anchor
        return "/"

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((perf_counter() - started) * 1000, 2)

    def _result(
        self,
        component: str,
        status: str,
        message: str,
        metadata: dict[str, Any],
        response_time_ms: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source": self.SOURCE,
            "component": component,
            "status": status,
            "message": message,
            "metadata": metadata,
        }
        if response_time_ms is not None:
            payload["response_time_ms"] = response_time_ms
        return payload
