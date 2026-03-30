"""surcharge.selectors — read-only queries."""
from __future__ import annotations
from django.db.models import QuerySet
from django.utils import timezone
from .models import TaxRule, ShippingRule, FeeRule


def _active_qs(qs: QuerySet) -> QuerySet:
    now = timezone.now()
    return (
        qs.filter(is_active=True)
        .filter(__import__("django.db.models", fromlist=["Q"]).Q(start_date__isnull=True) | __import__("django.db.models", fromlist=["Q"]).Q(start_date__lte=now))
        .filter(__import__("django.db.models", fromlist=["Q"]).Q(end_date__isnull=True)   | __import__("django.db.models", fromlist=["Q"]).Q(end_date__gte=now))
    )


def get_active_tax_rules() -> QuerySet:
    return _active_qs(TaxRule.objects.prefetch_related("categories")).order_by("priority")


def get_active_shipping_rules() -> QuerySet:
    return _active_qs(ShippingRule.objects.all()).order_by("priority")


def get_active_fee_rules() -> QuerySet:
    return _active_qs(FeeRule.objects.all()).order_by("priority")


def get_all_tax_rules() -> QuerySet:
    return TaxRule.objects.prefetch_related("categories").order_by("priority", "name")


def get_all_shipping_rules() -> QuerySet:
    return ShippingRule.objects.order_by("priority", "name")


def get_all_fee_rules() -> QuerySet:
    return FeeRule.objects.order_by("priority", "name")
