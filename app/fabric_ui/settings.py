"""Django settings. Environment specific values come only from environment variables."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_list(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


DEBUG = _env_bool("DJANGO_DEBUG")

# Empty in production unless set; Django refuses to sign anything with an empty key.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY and DEBUG:
    SECRET_KEY = "insecure-local-development-only"

ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Local development only: fake Easy Auth principal (see core.dev_auth). Synthetic defaults.
DEV_AUTH_ENABLED = _env_bool("DEV_AUTH_ENABLED")
if DEV_AUTH_ENABLED and not DEBUG:
    raise ImproperlyConfigured("DEV_AUTH_ENABLED requires DJANGO_DEBUG to be true.")
DEV_AUTH_ROLES = _env_list("DEV_AUTH_ROLES") or ["viewer"]
DEV_AUTH_NAME = os.environ.get("DEV_AUTH_NAME", "Dev User")
DEV_AUTH_EMAIL = os.environ.get("DEV_AUTH_EMAIL", "dev.user@example.test")
DEV_AUTH_OBJECT_ID = os.environ.get("DEV_AUTH_OBJECT_ID", "00000000-0000-0000-0000-000000000001")

# Per environment config files (branding now; display config in M4).
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR") or BASE_DIR.parent / "config")
BRANDING_CONFIG = Path(os.environ.get("BRANDING_CONFIG") or CONFIG_DIR / "branding.example.yaml")
BRANDING_ASSETS_DIR = CONFIG_DIR / "branding"

# No django.contrib.auth or sessions: identity comes only from Entra via Easy Auth (D16).
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "core",
    "audit",
    "support",
    "catalog",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.correlation.CorrelationIdMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.EasyAuthMiddleware",
]
if DEV_AUTH_ENABLED:
    MIDDLEWARE.insert(0, "core.dev_auth.DevPrincipalMiddleware")

ROOT_URLCONF = "fabric_ui.urls"
WSGI_APPLICATION = "fabric_ui.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "core.context_processors.layout",
            ],
        },
    },
]

# SQLite for local development and unit tests. Azure SQL (mssql-django) is configured in M2/M7.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static", ("branding", BRANDING_ASSETS_DIR)]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Security. App Service terminates TLS and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"correlation_id": {"()": "core.correlation.CorrelationIdFilter"}},
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s [%(correlation_id)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["correlation_id"],
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
