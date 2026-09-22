import os
from pathlib import Path
import environ
import structlog
from celery.schedules import crontab

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialize environ
env = environ.Env()
# Read .env file from the root directory
environ.Env.read_env(os.path.join(BASE_DIR.parent, '.env'))

# Quick-start development settings - unsuitable for production
SECRET_KEY = env('DJANGO_SECRET_KEY', default='django-insecure-key-for-local-use')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ENABLE_DJANGO_ADMIN = env.bool('ENABLE_DJANGO_ADMIN', default=DEBUG)

ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'health_check',
    'drf_spectacular',
    # Required by the DatabaseScheduler that docker-compose.prod.yml already
    # asks celery for (`-B --scheduler django_celery_beat.schedulers:
    # DatabaseScheduler`). The package was in requirements.txt but the app was
    # never installed, so that scheduler could not import its own models and
    # beat failed at startup — which is why no scheduled task has been firing.
    # Adding it here brings its migrations in; they run under RUN_MIGRATIONS.
    'django_celery_beat',

    # Local apps
    'core',
    'apps.accounts',
    'apps.catalog',
    'apps.inventory',
    'apps.pricing',
    'apps.cart',
    'apps.orders',
    'apps.payments',
    'apps.pos',
    'apps.surcharge',
    'apps.returns',
    'apps.notifications',
    'apps.features',
    'apps.shipping',
    'apps.reviews',
    'apps.invoices',
    'apps.health',
    'apps.banners',
    'apps.address',
    'apps.privacy',
    'audit',
]

MIDDLEWARE = [
    # 1. Tracing first — stamps request_id on every request
    'core.middleware.RequestTracingMiddleware',
    # 2. Django / third-party stack
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'audit.middleware.AuditRequestContextMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 3. Per-request structured logging (after auth so user is available)
    'core.middleware.LoggingMiddleware',
    # 4. Last-resort handler for non-DRF code paths
    'core.middleware.ErrorHandlingMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
# Placeholder config as requested
DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///db.sqlite3')
}

# Persistent database connections.
# Django defaults CONN_MAX_AGE to 0, which opens and tears down a new
# connection on every single request (5-30ms of TCP+TLS overhead each time).
# Each gunicorn worker holds one connection open, so keep
# (workers * threads) comfortably below the server's max_connections.
# CONN_HEALTH_CHECKS pings a pooled connection before reuse so a connection
# dropped server-side surfaces as a retry rather than a 500.
DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE', default=60)
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = env("STATIC_URL", default="/static/")
STATIC_ROOT = Path(env("DJANGO_STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", default=str(BASE_DIR / "media")))
IMAGE_UPLOAD_MAX_BYTES = env.int("IMAGE_UPLOAD_MAX_BYTES", default=5 * 1024 * 1024)
IMAGE_UPLOAD_ALLOWED_MIME_TYPES = env.list(
    "IMAGE_UPLOAD_ALLOWED_MIME_TYPES",
    default=["image/jpeg", "image/png", "image/webp"],
)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# DRF Settings
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'EXCEPTION_HANDLER': 'core.exceptions.global_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardResultsPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    # Throttle rates.
    #
    # `anon` is keyed by client IP (DRF reads X-Forwarded-For, which nginx sets
    # correctly). 300/hour was far too low for a storefront, for a reason that
    # is easy to miss in testing: Indian mobile carriers run CGNAT, so hundreds
    # or thousands of subscribers share a single public IP -- and therefore a
    # single bucket. Once it was spent, every one of those users got 429 on
    # every API call. In a client-rendered SPA a 429 does not surface as an
    # error page; it surfaces as a blank or half-empty screen. And because the
    # bucket resets hourly, the site appeared to heal itself and then break
    # again, which is exactly the "works sometimes, worse at busy times"
    # symptom that was reported.
    #
    # 3000/hour is still a real ceiling against scraping, but it is no longer
    # trippable by one busy mobile tower. The endpoints that actually attract
    # abuse -- login, registration, password reset, contact, reviews -- carry
    # their own much tighter scoped rates below and are unaffected by this.
    #
    # If it needs tuning again, measure first:
    #     grep -c ' 429 ' /var/log/nginx/access.log
    'DEFAULT_THROTTLE_RATES': {
        'anon': '3000/hour',
        # Keyed by user id, not IP, so this is genuinely per-person and CGNAT
        # does not apply. Raised alongside `anon` so a signed-in customer is
        # never limited more tightly than an anonymous one -- which is what
        # 1000 vs 3000 would otherwise mean.
        'user': '5000/hour',
        'auth_login': '30/hour',
        'auth_register': '15/hour',
        'auth_forgot_password': '10/hour',
        'contact_form': '20/hour',
        'newsletter_subscribe': '30/hour',
        'review_submit': '20/hour',
        'review_write': '20/hour',
        'review_vote': '60/hour',
    },
}

# JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': env('DJANGO_SECRET_KEY', default='django-insecure-key-for-local-use'),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_PAIR_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenObtainPairSerializer',
}

# Redis & Celery Config
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/1')

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}


CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=REDIS_URL)
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
# Razorpay credentials.
#
# RazorpayProvider._load_runtime_config() reads these as its base and lets an
# AppSetting / ProviderConfig row in the database override them, so the admin
# stays the primary place to manage keys. Until now the settings half of that
# pair did not exist: the provider did getattr(settings, "RAZORPAY_KEY_ID", "")
# against a name nothing defined, so putting the keys in .env looked reasonable
# and did precisely nothing. Defined here so both routes work.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")

RAZORPAY_STALE_ORDER_TIMEOUT_MINUTES = env.int("RAZORPAY_STALE_ORDER_TIMEOUT_MINUTES", default=20)
# 300s tied health.run_server_health_checks for the busiest slot in the whole
# schedule. Stale-order expiry is a janitorial sweep; it does not need to run
# twelve times an hour on a single-core box.
RAZORPAY_STALE_CLEANUP_INTERVAL_SECONDS = env.int("RAZORPAY_STALE_CLEANUP_INTERVAL_SECONDS", default=1800)

# Celery Beat — periodic tasks
# ── Health monitoring configuration ───────────────────────────
#
# HEALTH_API_BASE_URL was previously not defined at all, so
# apps/health/services.py fell through to its hard-coded default of
# "http://127.0.0.1:8000/api". That default is evaluated *inside the
# celery_worker container*, where nothing listens on port 8000 -- gunicorn
# lives in a different container. Every run of health.run_api_health_checks
# therefore produced nothing but connection errors, and did so every two
# minutes, forever. The reachable address is the compose service name.
# Master switch for the in-app health-monitoring subsystem (the three health.*
# beat tasks and the rows they write). Off by default.
#
# Not primarily a performance setting -- the tasks cost well under 1% of a core.
# The reason it defaults off is that a monitor running on the box it monitors
# cannot report that box being down: when the server falls over, these tasks
# fall over with it and the dashboard silently goes stale. External uptime
# monitoring hitting /health/server does the same job, better, from outside the
# failure domain, and costs this box nothing.
#
# The models, views, admin dashboard and tasks all remain intact. Set
# HEALTH_MONITORING_ENABLED=true to turn collection back on.
HEALTH_MONITORING_ENABLED = env.bool("HEALTH_MONITORING_ENABLED", default=False)

HEALTH_API_BASE_URL = env("HEALTH_API_BASE_URL", default="http://backend:8000/api")
HEALTH_API_TIMEOUT_SECONDS = env.float("HEALTH_API_TIMEOUT_SECONDS", default=3.0)

# The previous default endpoint list (/v1/catalog/health/, /v1/cart/health/,
# /v1/checkout/health/, /v1/system/ping/) matched no route in this codebase.
# These two do, and they answer the two different questions worth asking:
#   /v1/health-check/       - no DB, no cache. Is gunicorn routing at all?
#   /v1/catalog/categories/ - a real read through DRF + ORM + serializer.
# The in-process ServerHealthService already covers DB/cache/disk, so there is
# no value in re-checking those over HTTP.
HEALTH_API_ENDPOINTS = env.list(
    "HEALTH_API_ENDPOINTS",
    default=["/v1/health-check/", "/v1/catalog/categories/"],
)

# How long persisted HealthCheckResult rows are kept. Nothing pruned this table
# before; at the old intervals it grew by roughly 13,000 rows a day, across
# four indexes, forever, and the resulting autovacuum churn is a real and
# steadily growing CPU cost on a small box.
HEALTH_RESULT_RETENTION_DAYS = env.int("HEALTH_RESULT_RETENTION_DAYS", default=14)

# ── Celery beat schedule ──────────────────────────────────────
#
# Every interval here is a standing CPU cost paid forever, on an idle site, on
# whatever hardware production runs on. The previous schedule ran 157 task
# executions an hour with no visitors present -- and none of them had ever
# executed in local development, because docker-compose.dev.yml has no
# celery_beat service. That is the whole "fine on localhost, hot on the
# server" gap.
#
# Intervals are env-driven so they can be tightened on bigger hardware without
# a code change. The defaults are sized for a 1 vCPU box.
HEALTH_SERVER_CHECK_INTERVAL_SECONDS = env.int("HEALTH_SERVER_CHECK_INTERVAL_SECONDS", default=300)
HEALTH_API_CHECK_INTERVAL_SECONDS = env.int("HEALTH_API_CHECK_INTERVAL_SECONDS", default=600)
HEALTH_PAYMENT_CHECK_INTERVAL_SECONDS = env.int("HEALTH_PAYMENT_CHECK_INTERVAL_SECONDS", default=900)
NOTIFICATION_RETRY_INTERVAL_SECONDS = env.int("NOTIFICATION_RETRY_INTERVAL_SECONDS", default=900)
NOTIFICATION_RETRY_LOGS_INTERVAL_SECONDS = env.int("NOTIFICATION_RETRY_LOGS_INTERVAL_SECONDS", default=1800)

# ── Birthday / anniversary gift coupons ───────────────────────
#
# Off by default. Switching this on starts issuing real discounts on its own,
# so it is an explicit decision per environment rather than something that
# begins the moment the code deploys. Run the sweep with dry_run=True first.
#
# The sweep costs one indexed query per occasion per day. The terms live here
# so the gift can be re-priced without a deploy; coupons already issued keep
# the terms they were minted with, which is the correct behaviour — a customer
# who was told 15% gets 15%.
OCCASION_GIFTS_ENABLED = env.bool("OCCASION_GIFTS_ENABLED", default=False)
# How many days ahead of the date the email goes out. Enough time to order and
# have it arrive; a gift that lands on the morning of is a near-miss.
OCCASION_GIFT_LEAD_DAYS = env.int("OCCASION_GIFT_LEAD_DAYS", default=3)
OCCASION_GIFT_PERCENT = env.int("OCCASION_GIFT_PERCENT", default=15)
# Rupee ceiling on the discount. 0 means uncapped — think before setting that.
OCCASION_GIFT_MAX_DISCOUNT = env.int("OCCASION_GIFT_MAX_DISCOUNT", default=500)
OCCASION_GIFT_MIN_ORDER_VALUE = env.int("OCCASION_GIFT_MIN_ORDER_VALUE", default=0)
# Days after the occasion that the coupon stays live.
OCCASION_GIFT_VALID_DAYS = env.int("OCCASION_GIFT_VALID_DAYS", default=14)

CELERY_BEAT_SCHEDULE = {
    "retry-pending-notifications": {
        "task":     "notifications.retry_pending",
        "schedule": NOTIFICATION_RETRY_INTERVAL_SECONDS,    # was 300
    },
    "retry-failed-notification-logs": {
        "task": "notifications.retry_failed_logs",
        "schedule": NOTIFICATION_RETRY_LOGS_INTERVAL_SECONDS,  # was 600
    },
    "notification-provider-health-check": {
        "task": "notifications.provider_health_check",
        "schedule": 3600,  # was 1800
    },
    # New: bounds the HealthCheckResult table. Runs once a day, off-peak IST.
    # Stays scheduled even when collection is disabled -- there is existing
    # history to drain, and an empty sweep costs one indexed query a day.
    "health-prune-results": {
        "task": "health.prune_health_results",
        "schedule": crontab(hour=20, minute=30),  # 02:00 IST
    },
    "shipping-refresh-token": {
        "task": "shipping.refresh_shiprocket_token",
        "schedule": 3600,
    },
    "shipping-reconcile-stuck": {
        "task": "shipping.reconcile_stuck_shipments",
        "schedule": 1800,  # was 900
    },
    "payments-expire-stale-razorpay-orders": {
        "task": "payments.expire_stale_razorpay_orders",
        "schedule": RAZORPAY_STALE_CLEANUP_INTERVAL_SECONDS,
    },
    # Birthday / anniversary gifts. CELERY_TIMEZONE is Asia/Kolkata, so this is
    # 08:00 IST -- late enough that the email is not sitting at the bottom of an
    # overnight inbox, early enough to be read before the day starts.
    #
    # Stays scheduled even when OCCASION_GIFTS_ENABLED is false; the task
    # returns immediately in that case. Scheduling it unconditionally means the
    # feature is turned on with an env var and a worker restart rather than a
    # code change, and the guard lives in one place.
    "issue-occasion-coupons": {
        "task": "pricing.issue_occasion_coupons",
        "schedule": crontab(hour=8, minute=0),
    },
}

# Collection tasks are added only when the subsystem is switched on.
#
# NOTE: beat runs the DatabaseScheduler, so this dict is synced *into* the
# database. Removing an entry here does not delete the PeriodicTask row it
# already created -- see the guard in apps/health/tasks.py, which is what
# actually stops a stale row from doing work.
if HEALTH_MONITORING_ENABLED:
    CELERY_BEAT_SCHEDULE.update({
        "health-server-checks": {
            "task": "health.run_server_health_checks",
            "schedule": HEALTH_SERVER_CHECK_INTERVAL_SECONDS,  # was 60
        },
        "health-api-checks": {
            "task": "health.run_api_health_checks",
            "schedule": HEALTH_API_CHECK_INTERVAL_SECONDS,  # was 120
        },
        "health-payment-checks": {
            "task": "health.run_payment_health_checks",
            "schedule": HEALTH_PAYMENT_CHECK_INTERVAL_SECONDS,  # was 120
        },
    })

# ── Email ──────────────────────────────────────────────────────
EMAIL_BACKEND    = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST       = env("EMAIL_HOST",    default="smtp.gmail.com")
EMAIL_PORT       = env("EMAIL_PORT",    default=587)
EMAIL_HOST_USER  = env("EMAIL_HOST_USER",  default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS    = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Aurora Blings <noreply@aurorablings.com>")
ADMINS_EMAIL     = env("ADMINS_EMAIL", default="")

# ── Payments: Cashfree ────────────────────────────────────────
CASHFREE_APP_ID = env("CASHFREE_APP_ID", default="")
CASHFREE_SECRET_KEY = env("CASHFREE_SECRET_KEY", default="")
CASHFREE_ENV = env("CASHFREE_ENV", default="sandbox")

# ── Cloudflare Turnstile ──────────────────────────────────────
TURNSTILE_ENABLED = env.bool("TURNSTILE_ENABLED", default=False)
TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY", default="")
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="")

# CORS (Development)
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Backend base URL (used for media absolute URLs in API responses)
BACKEND_URL = env("BACKEND_URL", default="http://localhost:8000")
PRIVACY_STORE_IP_ADDRESS = env.bool("PRIVACY_STORE_IP_ADDRESS", default=False)

# ── Shipping: NimbusPost ─────────────────────────────────────
NIMBUSPOST_BASE_URL = env("NIMBUSPOST_BASE_URL", default="https://api.nimbuspost.com/v1")
NIMBUSPOST_API_KEY = env("NIMBUSPOST_API_KEY", default="")
NIMBUSPOST_WEBHOOK_SECRET = env("NIMBUSPOST_WEBHOOK_SECRET", default="")
NIMBUSPOST_TIMEOUT_SECONDS = env.int("NIMBUSPOST_TIMEOUT_SECONDS", default=20)

# Notification dashboard controls
NOTIFICATION_MAX_RETRY = env.int("NOTIFICATION_MAX_RETRY", default=3)
NOTIFICATION_PROVIDER_TIMEOUT = env.int("NOTIFICATION_PROVIDER_TIMEOUT", default=15)
NOTIFICATION_HEALTHCHECK_ENABLED = env.bool("NOTIFICATION_HEALTHCHECK_ENABLED", default=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain_formatter': {
            '()': 'structlog.stdlib.ProcessorFormatter',
            'processor': structlog.dev.ConsoleRenderer(),
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'plain_formatter',
        },
    },
    'loggers': {
        'django':     {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
        'aurora_app': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': True},
        'core':       {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
    },
}
