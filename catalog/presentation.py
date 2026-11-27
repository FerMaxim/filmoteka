"""Suppress unapproved provider metadata without mutating works or personal entries."""

from copy import copy
from django.conf import settings
from .kinopoisk import PROVIDER
from .models import Work


def present(work):
    if (
        settings.KINOPOISK_DATA_APPROVED
        or not work.external_refs.filter(provider=PROVIDER).exists()
    ):
        return work
    restricted = copy(work)
    restricted.metadata_hidden = True
    restricted.title = f"Произведение №{work.pk}"
    restricted.kind = Work.Kind.OTHER
    restricted.year = None
    restricted.rating_kinopoisk = None
    restricted.rating_imdb = None
    restricted.poster_url = ""
    return restricted
