"""
notifications.views
~~~~~~~~~~~~~~~~~~~
Customer:
  GET  /notifications/              → my notification history
  GET  /notifications/{id}/         → detail + delivery logs
  POST /notifications/{id}/retry/   → retry a failed notification

Admin:
  GET  /notifications/admin/                      → all notifications
  POST /notifications/admin/trigger/              → manually fire an event (testing)
  GET  /notifications/admin/templates/            → list all templates
  POST /notifications/admin/templates/            → create template
  GET/PATCH/DELETE /notifications/admin/templates/{id}/
"""
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Q, Count, Max
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import csv
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

from apps.accounts.permissions import IsStaffOrAdmin
from core.response import success_response, error_response
from core.exceptions import NotFoundError
from core.logging import get_logger
from core.turnstile import verify_turnstile_token, get_client_ip

from . import selectors, services
from .models import (
    NotificationLog,
    NotificationLogStatus,
    NotificationProviderSettings,
    NotificationTemplate,
    NotifySubscription,
    ContactQuery,
    ContactQueryStatus,
)
from .serializers import (
    NotificationSerializer, NotificationTemplateSerializer, TriggerEventSerializer,
    ContactFormSerializer, AdminContactQuerySerializer,
    NotifySubscriptionWriteSerializer, NotifySubscriptionSerializer, AdminNotifySubscriptionSerializer,
    NotificationLogListSerializer,
    NotificationLogDetailSerializer,
    ProviderStatusSerializer,
)
from apps.catalog import selectors as catalog_selectors
from .services.email_service import EmailService, EmailConfigError
from .services import retry_service, stats_service, provider_health_service
from . import email_service as notification_email_service

logger = get_logger(__name__)


class NotifySubscriptionCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = NotifySubscriptionWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        product = catalog_selectors.get_product_by_id(
            serializer.validated_data["product_id"],
            published_only=not request.user.is_staff,
        )
        if not product:
            raise NotFoundError("Product not found.")

        row, created = services.create_notify_subscription(
            product=product,
            user=request.user if request.user.is_authenticated else None,
            name=serializer.validated_data.get("name", ""),
            email=serializer.validated_data.get("email", ""),
            phone=serializer.validated_data.get("phone", ""),
        )
        payload = NotifySubscriptionSerializer(row).data
        if created:
            return success_response(data=payload, message="Notify subscription created.", status_code=status.HTTP_201_CREATED)
        return error_response(
            message="Subscription already exists.",
            error_code="already_subscribed",
            errors={"detail": "You are already subscribed for this product."},
            status_code=status.HTTP_409_CONFLICT,
        )


class NotifySubscriptionUnsubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, token):
        ok = services.unsubscribe_notify_subscription(token=token)
        if not ok:
            return error_response(
                message="Invalid or inactive unsubscribe token.",
                error_code="invalid_token",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return success_response(message="You have been unsubscribed from stock alerts.")


class AdminNotifySubscriptionListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = NotifySubscription.objects.select_related("product", "user").all()

        product_id = request.query_params.get("product_id")
        if product_id:
            qs = qs.filter(product_id=product_id)

        is_notified = request.query_params.get("is_notified")
        if is_notified in ("true", "false"):
            qs = qs.filter(is_notified=(is_notified == "true"))

        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(product__name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(user__email__icontains=search)
                | Q(name__icontains=search)
            )

        qs = qs.order_by("-created_at")[:500]
        return success_response(data=AdminNotifySubscriptionSerializer(qs, many=True).data)


class AdminNotifySubscriptionMarkNotifiedView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return error_response(
                message="ids is required.",
                error_code="validation_error",
                errors={"ids": ["Provide a non-empty list of IDs."]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        updated = NotifySubscription.objects.filter(id__in=ids).update(is_notified=True, is_active=False)
        return success_response(data={"updated": updated}, message="Selected requests marked as notified.")


class AdminNotifySubscriptionMarkAllNotifiedView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        qs = NotifySubscription.objects.filter(is_notified=False, is_active=True)

        product_id = request.data.get("product_id")
        if product_id:
            qs = qs.filter(product_id=product_id)

        updated = qs.update(is_notified=True, is_active=False)
        return success_response(data={"updated": updated}, message="All pending requests marked as notified.")


class AdminNotifySubscriptionExportView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = NotifySubscription.objects.select_related("product", "user").order_by("-created_at")[:2000]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="notify_subscriptions.csv"'
        writer = csv.writer(response)
        writer.writerow(["Product", "User/Email", "Phone", "Status", "Created At"])
        for row in qs:
            who = row.user.email if row.user_id and row.user else row.email
            writer.writerow([
                row.product.name,
                who,
                row.phone,
                "Notified" if row.is_notified else "Pending",
                row.created_at.isoformat(),
            ])
        return response


# ─────────────────────────────────────────────────────────────
#  Customer
# ─────────────────────────────────────────────────────────────

class MyNotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get("limit", 30))
        notifs = selectors.get_notifications_for_user(request.user, limit=limit)
        return success_response(data=NotificationSerializer(notifs, many=True).data)


class MyNotificationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, notif_id):
        notif = selectors.get_notification_by_id(notif_id)
        if not notif or (notif.user and notif.user != request.user):
            raise NotFoundError("Notification not found.")
        return success_response(data=NotificationSerializer(notif).data)


class RetryNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notif_id):
        notif = selectors.get_notification_by_id(notif_id)
        if not notif or (notif.user and notif.user != request.user):
            raise NotFoundError("Notification not found.")
        result = services.retry_notification(str(notif_id))
        if not result:
            return error_response(message="Cannot retry this notification.", status_code=400, error_code="retry_limit")
        return success_response(data=NotificationSerializer(result).data, message="Retry queued.")


# ─────────────────────────────────────────────────────────────
#  Admin
# ─────────────────────────────────────────────────────────────

class AdminNotificationListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        notifs = selectors.get_all_notifications(
            status=request.query_params.get("status"),
            channel=request.query_params.get("channel"),
            event=request.query_params.get("event"),
            limit=int(request.query_params.get("limit", 50)),
        )
        return success_response(data=NotificationSerializer(notifs, many=True).data)


class AdminTriggerEventView(APIView):
    """Fire a notification event manually — useful for testing templates."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = TriggerEventSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        notifications = services.trigger_event(
            event=data["event"],
            context=data.get("context", {}),
            recipient_email=data.get("recipient_email", ""),
            recipient_phone=data.get("recipient_phone", ""),
        )
        return success_response(
            data=NotificationSerializer(notifications, many=True).data,
            message=f"Triggered {len(notifications)} notification(s).",
        )


class ContactFormNotificationView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "contact_form"

    def post(self, request):
        serializer = ContactFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not verify_turnstile_token(
            token=data.get("turnstile_token", ""),
            remote_ip=get_client_ip(request),
            action="contact.form.submit",
        ):
            return error_response(
                message="CAPTCHA verification failed.",
                error_code="turnstile_verification_failed",
                errors={"turnstile_token": ["Invalid or missing CAPTCHA token."]},
                status_code=status.HTTP_400_BAD_REQUEST,
                request_id=getattr(request, "request_id", None),
            )

        contact_query = ContactQuery.objects.create(
            name=data["name"].strip(),
            email=data["email"].strip().lower(),
            phone=(data.get("phone") or "").strip(),
            subject=(data.get("subject") or "").strip(),
            message=data["message"].strip(),
            source="web",
        )

        from apps.features import services as feature_services
        from .events import NotificationEvent

        smtp = feature_services.get_setting("email.smtp", default={}) or {}
        support_email = str(smtp.get("reply_to") or smtp.get("username") or "").strip()
        if not support_email:
            support_email = "connect@aurorablings.com"

        recipients = []
        for email in [support_email, str(getattr(settings, "ADMINS_EMAIL", "") or "").strip()]:
            if email and email not in recipients:
                recipients.append(email)
        if not recipients:
            recipients = [support_email]

        notifications = []
        for admin_email in recipients:
            notifications.extend(
                services.trigger_event(
                    event=NotificationEvent.CONTACT_FORM_SUBMITTED,
                    context={
                        "name": data["name"],
                        "email": data["email"],
                        "phone": data.get("phone", ""),
                        "subject": data.get("subject", ""),
                        "message": data["message"],
                    },
                    recipient_email=admin_email,
                )
            )

        # Send acknowledgement email to the query submitter.
        try:
            from apps.features import services as feature_services

            site_url = str(feature_services.get_setting("site.frontend_url", default="http://localhost:5173") or "http://localhost:5173").rstrip("/")
            html_body = render_to_string(
                "emails/contact_form_acknowledgement.html",
                context={
                    "name": data["name"],
                    "subject": data.get("subject", ""),
                    "message": data["message"],
                    "support_email": support_email,
                    "site_url": site_url,
                    "logo_url": notification_email_service._resolve_public_logo_url(),
                    "year": timezone.now().year,
                },
            )
            text_body = (
                f"Hi {data['name']},\n\n"
                "Thank you for contacting Aurora Blings. "
                "We have received your message and our team will get back to you shortly.\n\n"
                f"Subject: {data.get('subject') or 'General inquiry'}\n"
                f"Support Email: {support_email}\n\n"
                "Regards,\nAurora Blings Team"
            )
            EmailService.send_html_email(
                to_email=data["email"],
                subject="We’ve received your message 💚",
                html_body=html_body,
                text_body=text_body,
            )
        except EmailConfigError as exc:
            logger.warning("contact_ack_email_skipped", error=str(exc), email=data["email"])
        except Exception as exc:  # noqa: BLE001
            logger.exception("contact_ack_email_failed", error=str(exc), email=data["email"])

        return success_response(
            data={"queued": len(notifications), "query_id": str(contact_query.id)},
            message="Your message has been submitted.",
            status_code=status.HTTP_201_CREATED,
        )


class AdminContactQueryListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = ContactQuery.objects.all()

        status_value = (request.query_params.get("status") or "").strip().lower()
        if status_value in {ContactQueryStatus.NEW, ContactQueryStatus.READ, ContactQueryStatus.RESOLVED}:
            qs = qs.filter(status=status_value)

        is_read = request.query_params.get("is_read")
        if is_read in ("true", "false"):
            qs = qs.filter(is_read=(is_read == "true"))

        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(subject__icontains=search)
                | Q(message__icontains=search)
            )

        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        qs = qs.order_by("-created_at")[:500]
        return success_response(data=AdminContactQuerySerializer(qs, many=True).data)


class AdminContactQueryMarkReadView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return error_response(
                message="ids is required.",
                error_code="validation_error",
                errors={"ids": ["Provide a non-empty list of IDs."]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        updated = ContactQuery.objects.filter(id__in=ids, is_read=False).update(
            is_read=True,
            status=ContactQueryStatus.READ,
            read_at=timezone.now(),
        )
        return success_response(data={"updated": updated}, message="Selected contact queries marked as read.")


class AdminTemplateListCreateView(ListCreateAPIView):
    serializer_class   = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    queryset           = NotificationTemplate.objects.all().order_by("event", "channel")


class AdminTemplateDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class   = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    queryset           = NotificationTemplate.objects.all()
    http_method_names  = ["get", "patch", "delete"]


class AdminNotificationDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        range_key = (request.query_params.get("range") or "").strip() or None
        date_from = (request.query_params.get("date_from") or "").strip() or None
        date_to = (request.query_params.get("date_to") or "").strip() or None

        stats = stats_service.get_notification_stats(range_key=range_key, date_from=date_from, date_to=date_to)
        providers = provider_health_service.get_provider_status_summary()
        template_usage = (
            NotificationLog.objects.values("template_name")
            .exclude(template_name="")
            .annotate(
                sends=Count("id"),
                success_count=Count("id", filter=Q(status=NotificationLogStatus.SENT)),
                failure_count=Count("id", filter=Q(status=NotificationLogStatus.FAILED)),
                last_used=Max("created_at"),
            )
            .order_by("-sends")[:10]
        )
        recent_failures_qs = NotificationLog.objects.filter(status=NotificationLogStatus.FAILED).order_by("-created_at")[:8]

        usage_payload = [
            {
                "template_code": row["template_name"],
                "sends": row["sends"],
                "success_count": row["success_count"],
                "failure_count": row["failure_count"],
                "last_used": row["last_used"],
            }
            for row in template_usage
        ]

        return success_response(
            data={
                "stats": stats,
                "provider_status": ProviderStatusSerializer(providers, many=True).data,
                "recent_failures": NotificationLogListSerializer(recent_failures_qs, many=True).data,
                "template_usage": usage_payload,
            }
        )


class AdminNotificationLogsView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = NotificationLog.objects.all().order_by("-created_at")

        search = (request.query_params.get("search") or "").strip()
        status_value = (request.query_params.get("status") or "").strip()
        channel = (request.query_params.get("channel") or "").strip()
        provider = (request.query_params.get("provider") or "").strip()
        notification_type = (request.query_params.get("notification_type") or "").strip()
        date_from = (request.query_params.get("date_from") or "").strip()
        date_to = (request.query_params.get("date_to") or "").strip()

        if search:
            qs = qs.filter(Q(recipient__icontains=search) | Q(subject__icontains=search) | Q(error_message__icontains=search))
        if status_value:
            qs = qs.filter(status=status_value)
        if channel:
            qs = qs.filter(channel=channel)
        if provider:
            qs = qs.filter(provider=provider)
        if notification_type:
            qs = qs.filter(notification_type=notification_type)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        page = max(int(request.query_params.get("page", 1) or 1), 1)
        page_size = min(max(int(request.query_params.get("page_size", 20) or 20), 1), 100)
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        rows = qs[start:end]

        return success_response(
            data={
                "items": NotificationLogListSerializer(rows, many=True).data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            }
        )


class AdminNotificationLogDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, log_id):
        log = NotificationLog.objects.select_related("notification", "created_by").filter(id=log_id).first()
        if not log:
            raise NotFoundError("Notification log not found.")
        return success_response(data=NotificationLogDetailSerializer(log).data)


class AdminNotificationLogRetryView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, log_id):
        try:
            retried = retry_service.retry_notification(str(log_id))
        except ValueError as exc:
            return error_response(
                message=str(exc),
                error_code="retry_not_allowed",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return success_response(data=NotificationLogDetailSerializer(retried).data, message="Notification retry completed.")


class AdminNotificationProvidersStatusView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        providers = provider_health_service.get_provider_status_summary()
        return success_response(data=ProviderStatusSerializer(providers, many=True).data)


class AdminNotificationProviderTestView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, provider_id):
        provider = NotificationProviderSettings.objects.filter(id=provider_id).first()
        if not provider:
            raise NotFoundError("Provider not found.")
        tested = provider_health_service.test_provider(provider)
        return success_response(
            data=ProviderStatusSerializer(tested).data,
            message="Provider test completed.",
        )


class AdminNotificationEmailPreviewTestView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        logo_url = notification_email_service._resolve_public_logo_url()
        parsed = urlparse(str(logo_url or ""))
        hostname = (parsed.hostname or "").lower()
        non_public_hosts = {"", "localhost", "127.0.0.1", "0.0.0.0", "backend", "db", "redis"}
        is_public_host = hostname not in non_public_hosts

        reachable = False
        http_status = None
        content_type = ""
        error_message = ""

        if logo_url:
            try:
                req = Request(
                    url=logo_url,
                    headers={
                        "User-Agent": "AuroraBlings-EmailPreviewCheck/1.0",
                        "Accept": "image/*,*/*;q=0.8",
                    },
                    method="GET",
                )
                with urlopen(req, timeout=8) as response:  # nosec B310 (admin diagnostic URL only)
                    http_status = getattr(response, "status", None) or response.getcode()
                    content_type = str(response.headers.get("Content-Type", "") or "")
                    reachable = 200 <= int(http_status or 0) < 400
            except HTTPError as exc:
                http_status = exc.code
                error_message = f"HTTP {exc.code}"
            except URLError as exc:
                error_message = str(getattr(exc, "reason", exc))
            except Exception as exc:  # noqa: BLE001
                error_message = str(exc)

        advice = "Logo URL looks good."
        if not logo_url:
            advice = "Logo URL is empty. Set Branding logo in admin settings."
        elif not is_public_host:
            advice = "Logo URL points to a local/internal host. Set BACKEND_URL to a public domain."
        elif not reachable:
            advice = "Logo URL is not reachable. Verify file path, domain, SSL, and network access."

        return success_response(
            data={
                "logo_url": logo_url,
                "is_public_host": is_public_host,
                "reachable": reachable,
                "http_status": http_status,
                "content_type": content_type,
                "error_message": error_message,
                "advice": advice,
            },
            message="Email preview URL test completed.",
        )


class AdminNotificationTemplateUsageView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = (
            NotificationLog.objects.values("template_name")
            .exclude(template_name="")
            .annotate(
                sends=Count("id"),
                success_count=Count("id", filter=Q(status=NotificationLogStatus.SENT)),
                failure_count=Count("id", filter=Q(status=NotificationLogStatus.FAILED)),
                last_used=Max("created_at"),
            )
            .order_by("-sends")
        )
        payload = [
            {
                "template_code": row["template_name"],
                "sends": row["sends"],
                "success_count": row["success_count"],
                "failure_count": row["failure_count"],
                "last_used": row["last_used"],
            }
            for row in qs
        ]
        return success_response(data=payload)
