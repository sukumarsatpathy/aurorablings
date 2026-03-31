import os
from pathlib import Path
import environ
import structlog

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

ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'health_check',
    'drf_spectacular',
    
    # Local apps
    'core',
    'apps.accounts',
    'apps.catalog',
    'apps.inventory',
    'apps.pricing',
    'apps.cart',
    'apps.orders',
    'apps.payments',
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
    'DEFAULT_THROTTLE_RATES': {
        'anon': '80/hour',
        'user': '800/hour',
        'auth_login': '30/hour',
        'auth_register': '15/hour',
        'auth_forgot_password': '10/hour',
        'contact_form': '20/hour',
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

# Celery Beat — periodic tasks
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    "retry-pending-notifications": {
        "task":     "notifications.retry_pending",
        "schedule": 300,    # every 5 minutes
    },
    "retry-failed-notification-logs": {
        "task": "notifications.retry_failed_logs",
        "schedule": 600,  # every 10 minutes
    },
    "notification-provider-health-check": {
        "task": "notifications.provider_health_check",
        "schedule": 1800,  # every 30 minutes
    },
    "health-server-checks": {
        "task": "health.run_server_health_checks",
        "schedule": 60,  # every 1 minute
    },
    "health-api-checks": {
        "task": "health.run_api_health_checks",
        "schedule": 120,  # every 2 minutes
    },
    "health-payment-checks": {
        "task": "health.run_payment_health_checks",
        "schedule": 120,  # every 2 minutes
    },
    "shipping-refresh-token": {
        "task": "shipping.refresh_shiprocket_token",
        "schedule": 3600,
    },
    "shipping-reconcile-stuck": {
        "task": "shipping.reconcile_stuck_shipments",
        "schedule": 900,
    },
}

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
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
        'aurora_app': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': True},
        'core': {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
    },
}
