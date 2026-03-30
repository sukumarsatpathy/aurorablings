# Notification + Invoice Implementation Notes

## New Settings Keys (AppSetting)
- `email.smtp` (json)
- `email.smtp.schema` (json)
- `notifications.settings` (json)
- `notifications.settings.schema` (json)
- `notifications.events` (json)
- `notifications.events.schema` (json)

## Supported Event Types
- `order.created`
- `order.shipped`
- `order.delivered`
- `user.forgot_password`
- `user.blocked`
- `contact.form.submitted`
- `product.notify_me`

## Notification Flow
1. App event/hook calls `NotificationService.create_notification(...)` (directly or through `trigger_event_task`).
2. Service checks global toggles (`notifications.settings`) and per-event toggles (`notifications.events`).
3. Service resolves template metadata from `NotificationTemplate` (`key`, `template_file`, `subject_template`) or default registry.
4. HTML body is rendered from whitelisted `templates/emails/*.html` files.
5. SMTP config is loaded at send-time from `email.smtp` and sent through dynamic Django SMTP backend.
6. Notification state is persisted in `Notification` with delivery attempts in `NotificationAttempt` (+ legacy `NotificationLog`).
7. Failures are retried asynchronously via Celery (`notifications.send_notification`, `notifications.retry_pending`, `notifications.resend_failed_notification`).

## Email Templates Added
- `backend/templates/emails/base.html`
- `backend/templates/emails/order_confirmation.html`
- `backend/templates/emails/shipping_confirmation.html`
- `backend/templates/emails/order_delivered.html`
- `backend/templates/emails/forgot_password.html`
- `backend/templates/emails/contact_form_notification.html`
- `backend/templates/emails/notify_me.html`
- `backend/templates/emails/account_blocked.html`

## Real Event Integrations Wired
- Order placement (`apps.orders.services.place_order`) -> `order.created`
- Order shipped (`apps.orders.services.mark_shipped`) -> `order.shipped`
- Order delivered (`apps.orders.services.mark_delivered`) -> `order.delivered`
- Forgot password (`apps.accounts.services.initiate_password_reset`) -> `user.forgot_password`
- Account lock on repeated failed login (`apps.accounts.services._record_failed_attempt`) -> `user.blocked`
- Back in stock (`apps.notifications.tasks.notify_back_in_stock_task`) -> `product.notify_me`
- Contact form API endpoint (`POST /api/v1/notifications/contact-form/`) -> `contact.form.submitted`

## Invoice Generation/Storage
- New app: `apps.invoices`
- Model: `Invoice` (`order` one-to-one, `invoice_number`, generated PDF `file`, metadata, timestamps)
- Service: `InvoiceService`
  - builds invoice context from real `Order` and `OrderItem` data
  - generates invoice number (`AB-INV-{order_number}`)
  - caches PDF in DB/file storage and reuses existing file unless regenerate is requested
- PDF strategy:
  - primary: WeasyPrint HTML->PDF
  - fallback: ReportLab renderer
- Template: `backend/templates/invoices/invoice.html`

## Customer Invoice Endpoint
- `GET /api/v1/orders/{order_id}/invoice/`
- Permission rules:
  - authenticated customer can only access own order invoice
  - staff/admin can access any order invoice
- Response: secure file stream as PDF attachment (`application/pdf`)

## Admin Invoice Integration
- Django admin (`apps.orders.admin.OrderAdmin`):
  - invoice column in list (`Download Invoice`)
  - invoice panel in detail
  - bulk action: `Generate invoices for selected orders`
- Custom admin React Orders page (`frontend/src/pages/admin/Orders.tsx`):
  - invoice button column
  - row actions: download invoice, regenerate invoice
  - detail modal invoice card: download + regenerate
- Admin regenerate API:
  - `POST /api/v1/orders/admin/{order_id}/invoice/regenerate/`

## Customer Orders UI Integration
- Account Orders page (`frontend/src/pages/account/AccountOrdersPage.tsx`):
  - `Download Invoice` action wired to secure backend endpoint
  - loading state while preparing/opening invoice URL

## API/Serializer Changes
- Order list/detail serializers now expose `invoice_url`
- Shipment serializer payload uses invoice URL fallback from invoice service when needed

## Future Extension Points
- Add WhatsApp/SMS channel implementations under notification channel dispatcher
- Add signed URL support for time-limited invoice links if required
- Add batch invoice pre-generation task for high-volume backfills
- Extend template registry with locale-specific template files

## Tests Added
- `backend/apps/notifications/tests.py`
  - event toggle on/off
  - SMTP config loading
  - notification creation
  - send success/failure
  - retry path
  - forgot-password template rendering
  - shipped template includes tracking + invoice URL
  - blocked template includes duration
- `backend/apps/invoices/tests.py`
  - PDF generation
  - customer own-invoice access allowed
  - customer other-invoice access denied
  - admin any-invoice access allowed
  - admin order list exposes invoice URL
  - regenerate endpoint updates existing invoice record
