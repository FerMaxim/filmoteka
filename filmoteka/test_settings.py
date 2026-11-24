from .test_postgresql.base import validate_target

validate_target()

from .settings import *  # noqa: E402,F403
from .settings import DATABASES  # noqa: E402

DATABASES = {
    "default": {
        **DATABASES["default"],
        "ENGINE": "filmoteka.test_postgresql",
        "PORT": "5432",
        "TEST": {"NAME": DATABASES["default"]["NAME"]},
    }
}
