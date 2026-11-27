import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")
ROOT_URLCONF = "filmoteka.urls"
INSTALLED_APPS = [
    "accounts",
    "catalog",
    "collection",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
LANGUAGE_CODE = "ru"
USE_TZ = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "filmoteka/templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ]
        },
    }
]
STATICFILES_DIRS = [BASE_DIR / "filmoteka/static"]

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/catalog/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Live access and images require explicit separate confirmations by operations.
KINOPOISK_ENABLED = os.environ.get("KINOPOISK_ENABLED") == "1"
KINOPOISK_DATA_APPROVED = os.environ.get("KINOPOISK_DATA_APPROVED") == "1"
KINOPOISK_POSTERS_APPROVED = os.environ.get("KINOPOISK_POSTERS_APPROVED") == "1"
KINOPOISK_API_KEY = os.environ.get("KINOPOISK_API_KEY", "")
KINOPOISK_REQUEST_BUDGET = int(os.environ.get("KINOPOISK_REQUEST_BUDGET", "450"))
