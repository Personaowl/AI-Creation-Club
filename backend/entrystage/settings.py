import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
VAR_DIR = Path(os.environ.get("ENTRYSTAGE_VAR_DIR", BASE_DIR / "var"))


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = os.environ.get("ENTRYSTAGE_DEBUG") == "1"
SECRET_KEY = os.environ.get("ENTRYSTAGE_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set ENTRYSTAGE_SECRET_KEY in the deployment environment.")
    SECRET_KEY = "entrystage-local-development-only"

ALLOWED_HOSTS = env_list("ENTRYSTAGE_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
CSRF_TRUSTED_ORIGINS = env_list("ENTRYSTAGE_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin.apps.SimpleAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "works",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "entrystage.urls"
WSGI_APPLICATION = "entrystage.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

if name := os.environ.get("ENTRYSTAGE_MYSQL_DATABASE"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": name,
            "USER": os.environ.get("ENTRYSTAGE_MYSQL_USER", ""),
            "PASSWORD": os.environ.get("ENTRYSTAGE_MYSQL_PASSWORD", ""),
            "HOST": os.environ.get("ENTRYSTAGE_MYSQL_HOST", "127.0.0.1"),
            "PORT": os.environ.get("ENTRYSTAGE_MYSQL_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
        }
    }
elif DEBUG:
    VAR_DIR.mkdir(parents=True, exist_ok=True)
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": VAR_DIR / "db.sqlite3"}}
else:
    raise ImproperlyConfigured("Set ENTRYSTAGE_MYSQL_DATABASE or enable local development mode.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
LOGIN_URL = "/"

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = VAR_DIR / "static"
MEDIA_ROOT = Path(os.environ.get("ENTRYSTAGE_UPLOAD_ROOT", VAR_DIR / "uploads"))
FILE_UPLOAD_PERMISSIONS = 0o600
UPLOAD_MAX_BYTES = int(os.environ.get("ENTRYSTAGE_MAX_UPLOAD_MB", "512")) * 1024 * 1024

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

ONLYOFFICE_URL = os.environ.get("ENTRYSTAGE_ONLYOFFICE_URL", "").rstrip("/")
ONLYOFFICE_SOURCE_ORIGIN = os.environ.get("ENTRYSTAGE_ONLYOFFICE_SOURCE_ORIGIN", "").rstrip("/")
ONLYOFFICE_BROWSER_SECRET = os.environ.get("ENTRYSTAGE_ONLYOFFICE_BROWSER_SECRET", "")
ONLYOFFICE_OUTBOX_SECRET = os.environ.get("ENTRYSTAGE_ONLYOFFICE_OUTBOX_SECRET", "")
ONLYOFFICE_OUTBOX_HEADER = os.environ.get("ENTRYSTAGE_ONLYOFFICE_OUTBOX_HEADER", "Authorization")
ONLYOFFICE_TICKET_AGE = 180
