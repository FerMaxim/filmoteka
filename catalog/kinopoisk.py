"""Bounded, server-only v2.2 adapter. No redirects, retries or image downloads."""

import json
import hashlib
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from django.conf import settings

PROVIDER = "kinopoisk_unofficial"
BASE = "https://kinopoiskapiunofficial.tech/api/v2.2/films"


class Unavailable(Exception):
    def __init__(self, status=0):
        self.status = status
        super().__init__("External catalog unavailable")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def enabled():
    return (
        settings.KINOPOISK_ENABLED
        and bool(settings.KINOPOISK_API_KEY)
        and settings.KINOPOISK_DATA_APPROVED
    )


def scope():
    return hashlib.sha256(settings.KINOPOISK_API_KEY.encode()).hexdigest()


def poster_url(value):
    if not isinstance(value, str) or len(value) > 1000:
        return ""
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError:
        return ""
    if (
        url.scheme == "https"
        and url.hostname
        in {"kinopoiskapiunofficial.tech", "st.kp.yandex.net", "avatars.mds.yandex.net"}
        and not url.username
        and not url.password
        and port in {None, 443}
    ):
        return value
    return ""


def number(value, low, high, integer=False):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite() or not low <= result <= high:
            return None
        if integer:
            return int(result) if result == int(result) else None
        return str(result.quantize(Decimal("0.1")))
    except (InvalidOperation, ValueError, OverflowError):
        return None


def candidate(raw):
    if not isinstance(raw, dict):
        return None
    ident = number(raw.get("kinopoiskId"), 1, 15000000, True)
    title = next(
        (
            value.strip()
            for key in ("nameRu", "nameOriginal", "nameEn")
            if isinstance(value := raw.get(key), str) and value.strip()
        ),
        "",
    )
    if ident is None or not title or len(title) > 300:
        return None
    source_type = raw.get("type")
    if not isinstance(source_type, str):
        source_type = ""
    return {
        "external_id": str(ident),
        "title": title,
        "kind": {
            "FILM": "film",
            "TV_SERIES": "series",
            "MINI_SERIES": "series",
            "TV_SHOW": "series",
        }.get(source_type, "other"),
        "source_type": source_type[:40],
        "year": number(raw.get("year"), 1800, 2200, True),
        "rating_kinopoisk": number(raw.get("ratingKinopoisk"), 0, 10),
        "rating_imdb": number(raw.get("ratingImdb"), 0, 10),
        "poster_url": poster_url(raw.get("posterUrlPreview") or raw.get("posterUrl")),
    }


def fetch(query=None, page=1, ident=None):
    if not enabled():
        raise Unavailable()
    if getattr(settings, "KINOPOISK_TEST_FIXTURES", False):
        from django.db import connection

        if connection.settings_dict["ENGINE"] != "filmoteka.test_postgresql":
            raise Unavailable()
        from tests.kinopoisk_fixtures import response

        return response(query, page, ident)
    url = BASE + (
        f"/{ident}" if ident else "?" + urlencode({"keyword": query, "page": page})
    )
    request = Request(
        url,
        headers={"X-API-KEY": settings.KINOPOISK_API_KEY, "Accept": "application/json"},
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=4) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise Unavailable()
        return json.loads(data)
    except HTTPError as error:
        raise Unavailable(error.code) from None
    except (URLError, OSError, ValueError):
        raise Unavailable() from None


def normalize_response(raw, ident=None):
    if ident:
        result = candidate(raw)
        if not result or result["external_id"] != str(ident):
            raise Unavailable()
        return {"items": [result], "pages": 1}
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("items"), list)
        or len(raw["items"]) > 20
    ):
        raise Unavailable()
    pages = number(raw.get("totalPages"), 0, 1000, True)
    if pages is None:
        raise Unavailable()
    items = {}
    for row in raw["items"]:
        item = candidate(row)
        if item:
            items.setdefault(item["external_id"], item)
    return {"items": list(items.values()), "pages": min(pages, 20)}
