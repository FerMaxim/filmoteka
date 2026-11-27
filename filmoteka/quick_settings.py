from .base_settings import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.dummy"}}

KINOPOISK_ENABLED = False
KINOPOISK_API_KEY = ""
KINOPOISK_DATA_APPROVED = False
