from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import requests
from django.utils import timezone

from apps.features.models import AppSetting
from apps.payments.models import PaymentTransaction, TransactionStatus, WebhookLog
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CashfreeConfig:
    enabled: bool
    environment: str
    app_id: str
    secret_key: str
    webhook_secret: str


class PaymentHealthService:
    """
    Health checks for Aurora Blings Cashfree integration.

    Returns a structured list of check results with safe masking for
    sensitive credentials.
    """

    CASHFREE_SETTING_KEYS = (
        "payment.cashfree",
        "payment-cashfree",
        "payment_cashfree",
        "cashfree",
    )
    VALID_ENVIRONMENTS = {"sandbox", "production"}
    WEBHOOK_WARNING_AFTER_MINUTES = 30
    FAILED_TREND_WINDOW_MINUTES = 30
    FAILED_TREND_DEGRADED_THRESHOLD = 5
    CONNECTIVITY_TIMEOUT_SECONDS = 8

    def run_checks(self) -> list[dict[str, Any]]:
        now = timezone.now()

        config, config_errors, raw_config = self._load_cashfree_config()
        config_result = self._check_cashfree_config(
            config=config,
            config_errors=config_errors,
            raw_config=raw_config,
            checked_at=now,
        )

        connectivity_result = self._check_cashfree_connectivity(config=config, checked_at=now)
        webhook_result = self._check_cashfree_webhook(checked_at=now)
        trend_result = self._check_cashfree_payment_trend(checked_at=now)

        return [
            config_result,
            connectivity_result,
            webhook_result,
            trend_result,
        ]

    def _load_cashfree_config(self) -> tuple[CashfreeConfig | None, list[str], dict[str, Any]]:
        errors: list[str] = []
        raw_config: dict[str, Any] = {}

        setting = (
            AppSetting.objects
            .filter(key__in=self.CASHFREE_SETTING_KEYS)
            .order_by("-updated_at")
            .first()
        )
        if not setting:
            errors.append(
                f"Cashfree AppSetting not found (tried: {', '.join(self.CASHFREE_SETTING_KEYS)})"
            )
            return None, errors, raw_config

        value = setting.typed_value

        if isinstance(value, dict):
            raw_config = value
        elif isinstance(value, str):
            value = value.strip()
            if not value:
                errors.append("Cashfree config is empty")
                return None, errors, raw_config
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    raw_config = parsed
                else:
                    errors.append("Cashfree config JSON must be an object")
                    return None, errors, raw_config
            except json.JSONDecodeError:
                errors.append("Cashfree config is not valid JSON")
                return None, errors, raw_config
        else:
            errors.append("Cashfree config has unsupported type")
            return None, errors, raw_config

        enabled_raw = raw_config.get("enabled")
        environment = str(raw_config.get("environment", "")).strip().lower()
        app_id = str(raw_config.get("app_id", "")).strip()
        secret_key = str(raw_config.get("secret_key", "")).strip()
        webhook_secret = str(raw_config.get("webhook_secret", "")).strip()

        enabled = self._coerce_bool(enabled_raw)
        if enabled is None:
            errors.append("'enabled' must be a boolean")
            enabled = False

        if environment not in self.VALID_ENVIRONMENTS:
            errors.append("'environment' must be one of: sandbox, production")

        if not app_id:
            errors.append("'app_id' is required")
        if not secret_key:
            errors.append("'secret_key' is required")
        if not webhook_secret:
            errors.append("'webhook_secret' is required")

        config = CashfreeConfig(
            enabled=enabled,
            environment=environment,
            app_id=app_id,
            secret_key=secret_key,
            webhook_secret=webhook_secret,
        )
        return config, errors, raw_config

    def _check_cashfree_config(
        self,
        *,
        config: CashfreeConfig | None,
        config_errors: list[str],
        raw_config: dict[str, Any],
        checked_at,
    ) -> dict[str, Any]:
        details = {
            "setting_keys": list(self.CASHFREE_SETTING_KEYS),
            "config_present": bool(raw_config),
            "masked_config": self._masked_config(config, raw_config),
        }

        if config_errors:
            return self._build_result(
                check="cashfree_config",
                status="degraded",
                message="Cashfree configuration is invalid",
                checked_at=checked_at,
                details={**details, "errors": config_errors},
            )

        if config and not config.enabled:
            return self._build_result(
                check="cashfree_config",
                status="warning",
                message="Cashfree is configured but disabled",
                checked_at=checked_at,
                details=details,
            )

        return self._build_result(
            check="cashfree_config",
            status="healthy",
            message="Cashfree configuration is valid",
            checked_at=checked_at,
            details=details,
        )

    def _check_cashfree_connectivity(self, *, config: CashfreeConfig | None, checked_at) -> dict[str, Any]:
        if not config:
            return self._build_result(
                check="cashfree_connectivity",
                status="warning",
                message="Connectivity check skipped because configuration is unavailable",
                checked_at=checked_at,
                details={"skipped": True, "reason": "missing_or_invalid_config"},
            )

        if not config.enabled:
            return self._build_result(
                check="cashfree_connectivity",
                status="warning",
                message="Connectivity check skipped because Cashfree is disabled",
                checked_at=checked_at,
                details={"skipped": True, "reason": "cashfree_disabled"},
            )

        base_url = (
            "https://api.cashfree.com/pg"
            if config.environment == "production"
            else "https://sandbox.cashfree.com/pg"
        )
        probe_ref = f"aurora-health-{int(time.time())}"
        probe_url = f"{base_url}/orders/{probe_ref}"

        headers = {
            "x-api-version": "2023-08-01",
            "x-client-id": config.app_id,
            "x-client-secret": config.secret_key,
            "Accept": "application/json",
        }

        started_at = time.perf_counter()
        try:
            response = requests.get(
                probe_url,
                headers=headers,
                timeout=self.CONNECTIVITY_TIMEOUT_SECONDS,
            )
            latency_ms = round((time.perf_counter() - started_at) * 1000, 2)

            # 2xx/4xx means the endpoint is reachable over network.
            reachable = response.status_code < 500
            if not reachable:
                return self._build_result(
                    check="cashfree_connectivity",
                    status="degraded",
                    message="Cashfree endpoint reachable but returned server error",
                    checked_at=checked_at,
                    details={
                        "reachable": True,
                        "latency_ms": latency_ms,
                        "http_status": response.status_code,
                    },
                )

            if response.status_code in (401, 403):
                return self._build_result(
                    check="cashfree_connectivity",
                    status="degraded",
                    message="Cashfree connectivity succeeded but credentials were rejected",
                    checked_at=checked_at,
                    details={
                        "reachable": True,
                        "latency_ms": latency_ms,
                        "http_status": response.status_code,
                    },
                )

            return self._build_result(
                check="cashfree_connectivity",
                status="healthy",
                message="Cashfree connectivity check succeeded",
                checked_at=checked_at,
                details={
                    "reachable": True,
                    "latency_ms": latency_ms,
                    "http_status": response.status_code,
                },
            )
        except requests.RequestException as exc:
            latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.warning("cashfree_connectivity_failed", error=str(exc))
            return self._build_result(
                check="cashfree_connectivity",
                status="degraded",
                message="Cashfree connectivity check failed",
                checked_at=checked_at,
                details={
                    "reachable": False,
                    "latency_ms": latency_ms,
                    "error": str(exc),
                },
            )

    def _check_cashfree_webhook(self, *, checked_at) -> dict[str, Any]:
        latest = (
            WebhookLog.objects
            .filter(provider="cashfree")
            .order_by("-created_at")
            .first()
        )

        if not latest:
            return self._build_result(
                check="cashfree_webhook",
                status="warning",
                message="No Cashfree webhook has been received yet",
                checked_at=checked_at,
                details={"last_webhook_at": None, "minutes_since_last_webhook": None},
            )

        age = checked_at - latest.created_at
        age_minutes = round(age.total_seconds() / 60, 2)

        if age > timedelta(minutes=self.WEBHOOK_WARNING_AFTER_MINUTES):
            return self._build_result(
                check="cashfree_webhook",
                status="warning",
                message="Cashfree webhook delay detected",
                checked_at=checked_at,
                details={
                    "last_webhook_at": latest.created_at.isoformat(),
                    "minutes_since_last_webhook": age_minutes,
                },
            )

        return self._build_result(
            check="cashfree_webhook",
            status="healthy",
            message="Cashfree webhook flow is recent",
            checked_at=checked_at,
            details={
                "last_webhook_at": latest.created_at.isoformat(),
                "minutes_since_last_webhook": age_minutes,
            },
        )

    def _check_cashfree_payment_trend(self, *, checked_at) -> dict[str, Any]:
        window_start = checked_at - timedelta(minutes=self.FAILED_TREND_WINDOW_MINUTES)
        failed_count = PaymentTransaction.objects.filter(
            provider="cashfree",
            status=TransactionStatus.FAILED,
            created_at__gte=window_start,
        ).count()

        status = "degraded" if failed_count > self.FAILED_TREND_DEGRADED_THRESHOLD else "healthy"
        message = (
            "Cashfree payment failure trend is degraded"
            if status == "degraded"
            else "Cashfree payment failure trend is within acceptable limits"
        )

        return self._build_result(
            check="cashfree_payment_trend",
            status=status,
            message=message,
            checked_at=checked_at,
            details={
                "window_minutes": self.FAILED_TREND_WINDOW_MINUTES,
                "failed_payments": failed_count,
                "degraded_threshold": self.FAILED_TREND_DEGRADED_THRESHOLD,
            },
        )

    def _masked_config(self, config: CashfreeConfig | None, raw_config: dict[str, Any]) -> dict[str, Any]:
        if not raw_config:
            return {}

        enabled = raw_config.get("enabled")
        environment = raw_config.get("environment")
        app_id = ""
        secret_key = ""
        webhook_secret = ""

        if config:
            app_id = config.app_id
            secret_key = config.secret_key
            webhook_secret = config.webhook_secret
        else:
            app_id = str(raw_config.get("app_id", ""))
            secret_key = str(raw_config.get("secret_key", ""))
            webhook_secret = str(raw_config.get("webhook_secret", ""))

        return {
            "enabled": enabled,
            "environment": environment,
            "app_id": self._mask_partial(app_id),
            "secret_key": self._mask_secret(secret_key),
            "webhook_secret": self._mask_secret(webhook_secret),
        }

    def _build_result(
        self,
        *,
        check: str,
        status: str,
        message: str,
        checked_at,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "check": check,
            "status": status,
            "message": message,
            "checked_at": checked_at.isoformat(),
            "details": details,
        }

    @staticmethod
    def _coerce_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        return None

    @staticmethod
    def _mask_partial(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"

    @staticmethod
    def _mask_secret(value: str) -> str:
        if not value:
            return ""
        return "*" * 8
