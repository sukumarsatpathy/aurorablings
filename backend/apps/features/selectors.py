"""features.selectors — read-only queries."""
from __future__ import annotations
from django.db.models import QuerySet, Prefetch
from .models import Feature, FeatureFlag, ProviderConfig, AppSetting


def get_all_features(*, category: str | None = None) -> QuerySet:
    qs = Feature.objects.prefetch_related(
        Prefetch("flag", queryset=FeatureFlag.objects.all()),
        Prefetch("provider_configs", queryset=ProviderConfig.objects.filter(is_active=True)),
    )
    if category:
        qs = qs.filter(category=category)
    return qs.order_by("category", "name")


def get_feature_by_code(code: str) -> Feature | None:
    try:
        return (
            Feature.objects
            .prefetch_related("flag", "provider_configs")
            .get(code=code)
        )
    except Feature.DoesNotExist:
        return None


def get_enabled_features() -> QuerySet:
    return Feature.objects.filter(
        flag__is_enabled=True,
        is_available=True,
    ).select_related("flag")


def get_provider_configs_for_feature(feature_code: str) -> QuerySet:
    return ProviderConfig.objects.filter(feature__code=feature_code).order_by("-is_active", "provider_key")


def get_all_settings(*, category: str | None = None, is_public: bool | None = None) -> QuerySet:
    qs = AppSetting.objects.all()
    if category:
        qs = qs.filter(category=category)
    if is_public is not None:
        qs = qs.filter(is_public=is_public)
    return qs.order_by("category", "key")
