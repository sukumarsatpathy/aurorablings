"""
features.views
~~~~~~~~~~~~~~
Public (read-only):
  GET /features/public-settings/     → all is_public AppSettings

Admin:
  GET  /features/                    → all features (+ flags)
  GET  /features/{code}/             → single feature
  POST /features/{code}/enable/      → enable feature
  POST /features/{code}/disable/     → disable feature
  POST /features/{code}/rollout/     → set rollout %
  GET  /features/{code}/providers/   → list provider configs (masked)
  POST /features/{code}/providers/   → set/update provider config
  POST /features/{code}/providers/activate/ → switch active provider

  GET         /features/settings/          → all AppSettings
  GET/PATCH   /features/settings/{key}/    → read + update single setting
  POST        /features/settings/bulk/     → bulk update
"""
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework import status
from django.core.files.storage import default_storage
import uuid
from pathlib import Path
from core.response import success_response, error_response
from core.exceptions import NotFoundError
from core.media import (
    MIME_TO_EXTENSION,
    build_media_url,
    validate_image_file,
)
from apps.accounts.permissions import IsStaffOrAdmin
from audit.models import ActorType, AuditAction
from audit.services.activity_logger import log_activity

from . import services, selectors
from .media_cleanup import cleanup_replaced_media, resolve_media_path, safe_delete_media_path
from .security import (
    MASKED_SETTING_VALUE,
    is_secret_setting,
    sanitize_settings_for_logs,
    sanitize_settings_for_response,
)
from .serializers import (
    FeatureSerializer, ProviderConfigReadSerializer,
    AppSettingSerializer, PublicSettingSerializer,
    PublicTrackingSettingsSerializer,
    FeatureWriteSerializer,
    AppSettingWriteSerializer,
    EnableFeatureSerializer, SetRolloutSerializer,
    SetProviderConfigSerializer, ActivateProviderSerializer,
    UpdateSettingSerializer, BulkUpdateSettingsSerializer,
)
from .models import Feature, FeatureFlag, AppSetting

# ─────────────────────────────────────────────────────────────
#  Public
# ─────────────────────────────────────────────────────────────

class PublicSettingsView(APIView):
    """No auth required. Returns all is_public AppSettings."""
    permission_classes = [AllowAny]

    def get(self, request):
        data = services.get_public_settings()
        turnstile = services.get_turnstile_config()
        data["turnstile_enabled"] = bool(turnstile.get("enabled"))
        data["turnstile_site_key"] = str(turnstile.get("site_key") or "")
        return success_response(data=data)


class PublicRuntimeSettingsView(APIView):
    """
    Minimal unauthenticated runtime config for storefront clients.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        turnstile = services.get_turnstile_config()
        return success_response(
            data={
                "turnstile_enabled": bool(turnstile.get("enabled")),
                "turnstile_site_key": str(turnstile.get("site_key") or ""),
            }
        )


class PublicTrackingSettingsView(APIView):
    """
    Public runtime tracking settings.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        data = services.get_clarity_runtime_config()
        serializer = PublicTrackingSettingsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return success_response(data=serializer.validated_data)


# ─────────────────────────────────────────────────────────────
#  Admin: Features
# ─────────────────────────────────────────────────────────────

class FeatureListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = selectors.get_all_features(category=request.query_params.get("category"))
        return success_response(data=FeatureSerializer(qs, many=True).data)

    def post(self, request):
        s = FeatureWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        feature = s.save()
        FeatureFlag.objects.get_or_create(
            feature=feature,
            defaults={"is_enabled": False, "rollout_percentage": 100},
        )
        return success_response(
            data=FeatureSerializer(feature).data,
            message="Feature created.",
            status_code=201,
        )


class FeatureDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, code):
        feature = selectors.get_feature_by_code(code)
        if not feature:
            raise NotFoundError(f"Feature '{code}' not found.")
        return success_response(data=FeatureSerializer(feature).data)

    def patch(self, request, code):
        feature = selectors.get_feature_by_code(code)
        if not feature:
            raise NotFoundError(f"Feature '{code}' not found.")
        s = FeatureWriteSerializer(feature, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        updated = s.save()
        return success_response(
            data=FeatureSerializer(updated).data,
            message="Feature updated.",
        )

    def delete(self, request, code):
        try:
            feature = Feature.objects.get(code=code)
        except Feature.DoesNotExist:
            raise NotFoundError(f"Feature '{code}' not found.")
        feature.delete()
        return success_response(message="Feature deleted.")


class FeatureEnableView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, code):
        s = EnableFeatureSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            flag = services.enable_feature(code, by_user=request.user, notes=s.validated_data["notes"])
        except services.FeatureNotFoundError as exc:
            raise NotFoundError(str(exc))
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.STATUS_CHANGE,
            entity_type="feature_flag",
            entity_id=code,
            description=f"Enabled feature '{code}'",
            metadata={"notes": s.validated_data["notes"]},
            request=request,
        )
        return success_response(message=f"Feature '{code}' enabled.")


class FeatureDisableView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, code):
        s = EnableFeatureSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            services.disable_feature(code, by_user=request.user, notes=s.validated_data["notes"])
        except services.FeatureNotFoundError as exc:
            raise NotFoundError(str(exc))
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.STATUS_CHANGE,
            entity_type="feature_flag",
            entity_id=code,
            description=f"Disabled feature '{code}'",
            metadata={"notes": s.validated_data["notes"]},
            request=request,
        )
        return success_response(message=f"Feature '{code}' disabled.")


class FeatureRolloutView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, code):
        s = SetRolloutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            services.set_rollout(code, s.validated_data["percentage"], by_user=request.user)
        except services.FeatureNotFoundError as exc:
            raise NotFoundError(str(exc))
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.UPDATE,
            entity_type="feature_flag",
            entity_id=code,
            description=f"Updated rollout for feature '{code}'",
            metadata={"rollout_percentage": s.validated_data["percentage"]},
            request=request,
        )
        return success_response(message=f"Rollout set to {s.validated_data['percentage']}% for '{code}'.")


# ─────────────────────────────────────────────────────────────
#  Admin: Provider Config
# ─────────────────────────────────────────────────────────────

class ProviderConfigListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, code):
        qs = selectors.get_provider_configs_for_feature(code)
        return success_response(data=ProviderConfigReadSerializer(qs, many=True).data)

    def post(self, request, code):
        s = SetProviderConfigSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            pc = services.set_provider_config(
                feature_code=code,
                provider_key=s.validated_data["provider_key"],
                config=s.validated_data["config"],
                activate=s.validated_data["activate"],
                by_user=request.user,
            )
        except services.FeatureNotFoundError as exc:
            raise NotFoundError(str(exc))
        entity_type = "payment_config" if code.startswith("payment") else "provider_config"
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.UPDATE,
            entity_type=entity_type,
            entity_id=f"{code}.{pc.provider_key}",
            description=f"Updated provider config for '{code}' ({pc.provider_key})",
            metadata={"feature": code, "provider_key": pc.provider_key, "is_active": pc.is_active, "config": pc.config},
            request=request,
        )
        return success_response(
            data=ProviderConfigReadSerializer(pc).data,
            message="Provider config saved.",
        )


class ProviderActivateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, code):
        s = ActivateProviderSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            pc = services.activate_provider(code, s.validated_data["provider_key"])
        except services.FeatureNotFoundError as exc:
            raise NotFoundError(str(exc))
        entity_type = "payment_config" if code.startswith("payment") else "provider_config"
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.STATUS_CHANGE,
            entity_type=entity_type,
            entity_id=f"{code}.{pc.provider_key}",
            description=f"Activated provider '{pc.provider_key}' for '{code}'",
            metadata={"feature": code, "provider_key": pc.provider_key},
            request=request,
        )
        return success_response(
            data=ProviderConfigReadSerializer(pc).data,
            message=f"Provider '{s.validated_data['provider_key']}' activated for '{code}'.",
        )


# ─────────────────────────────────────────────────────────────
#  Admin: App Settings
# ─────────────────────────────────────────────────────────────

class SettingListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = selectors.get_all_settings(
            category=request.query_params.get("category"),
            is_public=None,
        )
        payload = AppSettingSerializer(qs, many=True).data
        return success_response(data=sanitize_settings_for_response(payload))

    def post(self, request):
        s = AppSettingWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        setting = s.save(updated_by=request.user)
        entity_type = "seo_setting" if setting.category == "seo" else "setting"
        if "banner" in setting.key or "homepage" in setting.key:
            entity_type = "banner"
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.CREATE,
            entity_type=entity_type,
            entity_id=setting.key,
            description=f"Created app setting '{setting.key}'",
            metadata={
                **sanitize_settings_for_logs({setting.key: setting.value}),
                "status": "success",
                "category": setting.category,
                "value_type": setting.value_type,
            },
            request=request,
        )
        return success_response(
            data=sanitize_settings_for_response(AppSettingSerializer(setting).data),
            message="Setting created.",
            status_code=201,
        )


class SettingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, key):
        try:
            setting = AppSetting.objects.get(key=key)
        except AppSetting.DoesNotExist:
            raise NotFoundError(f"Setting '{key}' not found.")
        return success_response(data=sanitize_settings_for_response(AppSettingSerializer(setting).data))

    def patch(self, request, key):
        try:
            setting = AppSetting.objects.get(key=key)
        except AppSetting.DoesNotExist:
            raise NotFoundError(f"Setting '{key}' not found.")
        old_value = str(setting.value or "")
        s = AppSettingWriteSerializer(setting, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        incoming_value = s.validated_data.get("value")
        if is_secret_setting(key) and isinstance(incoming_value, str) and incoming_value.strip() == MASKED_SETTING_VALUE:
            s.validated_data.pop("value", None)
        value_changed = "value" in s.validated_data
        setting = s.save(updated_by=request.user)
        if value_changed:
            cleanup_replaced_media(old_value, setting.value)
        entity_type = "seo_setting" if setting.category == "seo" else "setting"
        if "banner" in setting.key or "homepage" in setting.key:
            entity_type = "banner"
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.UPDATE,
            entity_type=entity_type,
            entity_id=setting.key,
            description=f"Updated app setting '{setting.key}'",
            metadata={
                **sanitize_settings_for_logs({setting.key: setting.value if value_changed else ""}),
                "status": "success",
                "category": setting.category,
                "value_changed": value_changed,
            },
            request=request,
        )
        return success_response(
            data=sanitize_settings_for_response(AppSettingSerializer(setting).data),
            message="Setting updated.",
        )

    def delete(self, request, key):
        try:
            setting = AppSetting.objects.get(key=key)
        except AppSetting.DoesNotExist:
            raise NotFoundError(f"Setting '{key}' not found.")
        old_path = resolve_media_path(setting.value)
        entity_type = "seo_setting" if setting.category == "seo" else "setting"
        if "banner" in setting.key or "homepage" in setting.key:
            entity_type = "banner"
        metadata = {
            **sanitize_settings_for_logs([setting.key]),
            "status": "success",
            "category": setting.category,
            "value_changed": False,
        }
        setting.delete()
        safe_delete_media_path(old_path)
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.DELETE,
            entity_type=entity_type,
            entity_id=key,
            description=f"Deleted app setting '{key}'",
            metadata=metadata,
            request=request,
        )
        return success_response(message="Setting deleted.")


class SettingBulkUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = BulkUpdateSettingsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        input_settings = s.validated_data["settings"]
        result = services.bulk_set_settings(input_settings, by_user=request.user)
        safe_result = sanitize_settings_for_response(result)
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.UPDATE,
            entity_type="setting",
            entity_id="bulk",
            description=f"Bulk updated {len(safe_result)} app settings",
            metadata={
                **sanitize_settings_for_logs(input_settings),
                "status": "success",
            },
            request=request,
        )
        return success_response(data=safe_result, message=f"{len(safe_result)} settings updated.")


class SettingUploadView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return error_response(
                message="No file uploaded.",
                error_code="validation_error",
                errors={"file": ["This field is required."]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validated_upload = validate_image_file(upload)
        except Exception as exc:
            return error_response(
                message="Unsupported or invalid image file.",
                error_code="validation_error",
                errors={"file": [str(exc)]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        detected_mime = str(getattr(validated_upload, "validated_mime_type", "") or "").lower()
        extension = MIME_TO_EXTENSION.get(detected_mime.lower())
        if not extension:
            extension = Path(validated_upload.name).suffix.lower() or ".jpg"

        file_name = f"{uuid.uuid4().hex}{extension}"
        relative_path = f"settings/branding/{file_name}"
        stored_path = default_storage.save(relative_path, validated_upload)
        file_url = default_storage.url(stored_path)
        absolute_url = build_media_url(file_url, request=request)

        return success_response(
            message="File uploaded successfully.",
            data={
                # TODO(media-url-migration): phase clients onto a single canonical media URL field.
                # Keep both fields for backward compatibility in this release.
                "url": file_url,
                "absolute_url": absolute_url,
                "path": stored_path,
                "name": file_name,
                "size": validated_upload.size,
                "content_type": detected_mime,
            },
            status_code=status.HTTP_201_CREATED,
        )
