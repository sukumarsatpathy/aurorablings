from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from audit.models import ActorType, AuditAction
from audit.services.activity_logger import log_activity


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs) -> None:
    actor_type = ActorType.ADMIN if getattr(user, "role", "") == "admin" else ActorType.CUSTOMER
    if getattr(user, "role", "") == "staff":
        actor_type = ActorType.STAFF

    log_activity(
        user=user,
        actor_type=actor_type,
        action=AuditAction.LOGIN,
        entity_type="auth",
        entity_id=str(user.id),
        description=f"{actor_type.title()} logged in",
        metadata={"email": getattr(user, "email", "")},
        request=request,
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs) -> None:
    actor_type = ActorType.SYSTEM
    if user and getattr(user, "is_authenticated", False):
        actor_type = ActorType.ADMIN if getattr(user, "role", "") == "admin" else ActorType.CUSTOMER
        if getattr(user, "role", "") == "staff":
            actor_type = ActorType.STAFF

    log_activity(
        user=user if user and getattr(user, "is_authenticated", False) else None,
        actor_type=actor_type,
        action=AuditAction.LOGOUT,
        entity_type="auth",
        entity_id=str(user.id) if user and getattr(user, "is_authenticated", False) else None,
        description=f"{actor_type.title()} logged out",
        request=request,
    )


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs) -> None:
    email = (credentials or {}).get("username") or (credentials or {}).get("email") or ""
    log_activity(
        user=None,
        actor_type=ActorType.SYSTEM,
        action=AuditAction.LOGIN,
        entity_type="auth",
        entity_id=None,
        description="Login failed",
        metadata={"email": email, "status": "failed"},
        request=request,
    )


try:
    from django.db.models.signals import post_delete, post_save
    from apps.pricing.coupons.models import Coupon

    @receiver(post_save, sender=Coupon)
    def on_coupon_saved(sender, instance: Coupon, created: bool, **kwargs) -> None:
        action = AuditAction.CREATE if created else AuditAction.UPDATE
        log_activity(
            user=getattr(instance, "updated_by", None),
            actor_type=ActorType.SYSTEM,
            action=action,
            entity_type="coupon",
            entity_id=str(instance.id),
            description=f"Coupon {'created' if created else 'updated'}: {instance.code}",
            metadata={
                "code": instance.code,
                "type": instance.type,
                "value": instance.value,
                "is_active": instance.is_active,
            },
        )

    @receiver(post_delete, sender=Coupon)
    def on_coupon_deleted(sender, instance: Coupon, **kwargs) -> None:
        log_activity(
            user=None,
            actor_type=ActorType.SYSTEM,
            action=AuditAction.DELETE,
            entity_type="coupon",
            entity_id=str(instance.id),
            description=f"Coupon deleted: {instance.code}",
            metadata={"code": instance.code},
        )
except Exception:
    # Coupon model import can fail during early migration stages.
    pass
