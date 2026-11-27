"""Shared PostgreSQL cache, fenced leases and rolling per-key attempt budget."""

import hashlib
import json
import time
import unicodedata
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models.functions import Greatest
from django.utils import timezone
from . import kinopoisk as api
from .models import (
    ExternalRef,
    FetchLease,
    ProviderAttempt,
    ProviderBudget,
    SearchCache,
    Work,
)


class LocalDenied(api.Unavailable):
    """No provider request was made; do not change the provider backoff/cache."""


NOTICE = "Внешний поиск временно недоступен. Локальные произведения доступны."


def normalized_query(query):
    return " ".join(unicodedata.normalize("NFKC", query).casefold().split())


def cache_key(query, page):
    value = json.dumps(
        [api.PROVIDER, 1, normalized_query(query), page], ensure_ascii=False
    )
    return hashlib.sha256(value.encode()).hexdigest()


def reserve():
    now = timezone.now()
    scope = api.scope()
    with transaction.atomic():
        ProviderBudget.objects.get_or_create(
            scope=scope, defaults={"pause_until": now, "next_allowed_at": now}
        )
        state = ProviderBudget.objects.select_for_update().get(pk=scope)
        cutoff = now - timedelta(hours=24)
        ProviderAttempt.objects.filter(scope=scope, created_at__lte=cutoff).delete()
        limit = min(max(settings.KINOPOISK_REQUEST_BUDGET, 0), 450)
        if (
            state.pause_until > now
            or ProviderAttempt.objects.filter(scope=scope).count() >= limit
        ):
            raise LocalDenied()
        ProviderAttempt.objects.create(scope=scope, created_at=now)
        delay = max(0, (state.next_allowed_at - now).total_seconds())
        if delay > 1:
            raise LocalDenied()
        state.next_allowed_at = max(now, state.next_allowed_at) + timedelta(
            milliseconds=250
        )
        state.save(update_fields=["next_allowed_at"])
    if delay:
        time.sleep(delay)


def pause(status):
    seconds = {402: 86400, 429: 60, 401: 300, 403: 300}.get(status, 10)
    ProviderBudget.objects.filter(pk=api.scope()).update(
        pause_until=Greatest("pause_until", timezone.now() + timedelta(seconds=seconds))
    )


def cached(key):
    return SearchCache.objects.filter(pk=key, expires_at__gt=timezone.now()).first()


def claim(key):
    now = timezone.now()
    with transaction.atomic():
        FetchLease.objects.get_or_create(key=key, defaults={"expires_at": now})
        lease = FetchLease.objects.select_for_update().get(pk=key)
        if lease.expires_at > now:
            return None
        lease.token = uuid.uuid4()
        lease.expires_at = now + timedelta(seconds=15)
        lease.save()
        return lease.token


def result_for(key, *, query=None, page=1, ident=None):
    if not settings.KINOPOISK_DATA_APPROVED:
        raise api.Unavailable()
    result = cached(key)
    if result:
        return result.payload, result.fetched_at
    if not api.enabled():
        raise api.Unavailable()
    deadline = time.monotonic() + 6
    while not (token := claim(key)):
        result = cached(key)
        if result:
            return result.payload, result.fetched_at
        if time.monotonic() >= deadline:
            raise api.Unavailable()
        time.sleep(0.04)
    try:
        # Another owner may have published between the initial read and acquisition.
        result = cached(key)
        if result:
            return result.payload, result.fetched_at
        reserve()
        try:
            payload = api.normalize_response(
                api.fetch(query=query, page=page, ident=ident), ident
            )
        except api.Unavailable as error:
            pause(error.status)
            previous = SearchCache.objects.filter(pk=key).first()
            payload = {
                **(previous.payload if previous else {"items": [], "pages": 0}),
                "unavailable": True,
            }
        now = timezone.now()
        ttl = 10 if payload.get("unavailable") else (86400 if payload["items"] else 600)
        if ident and not payload.get("unavailable"):
            ttl = 30 * 86400
        with transaction.atomic():
            lease = FetchLease.objects.select_for_update().get(pk=key)
            if lease.token != token or lease.expires_at <= now:
                raise api.Unavailable()
            SearchCache.objects.update_or_create(
                key=key,
                defaults={
                    "payload": payload,
                    "fetched_at": now,
                    "expires_at": now + timedelta(seconds=ttl),
                },
            )
        return payload, now
    finally:
        FetchLease.objects.filter(pk=key, token=token).update(expires_at=timezone.now())


def search(query, page=1):
    if not settings.KINOPOISK_DATA_APPROVED:
        return {"items": [], "pages": 0}, NOTICE
    key = cache_key(query, page)
    try:
        payload, _ = result_for(key, query=normalized_query(query), page=page)
        if payload.get("unavailable"):
            raise api.Unavailable()
        return payload, ""
    except api.Unavailable:
        stale = SearchCache.objects.filter(pk=key).first()
        return (stale.payload if stale else {"items": [], "pages": 0}), NOTICE


def import_work(ident, query, page):
    if not settings.KINOPOISK_DATA_APPROVED:
        raise api.Unavailable()
    ref = (
        ExternalRef.objects.filter(provider=api.PROVIDER, external_id=str(ident))
        .select_related("work")
        .first()
    )
    if ref:
        return ref.work
    result = cached(cache_key(query, page))
    item = (
        next(
            (
                row
                for row in result.payload.get("items", [])
                if row["external_id"] == str(ident)
            ),
            None,
        )
        if result and not result.payload.get("unavailable")
        else None
    )
    fetched = result.fetched_at if result else None
    if item is None:
        payload, fetched = result_for("detail:" + str(ident), ident=ident)
        if payload.get("unavailable"):
            raise api.Unavailable()
        item = payload["items"][0]
    # Catalog import is atomic; HTTP invokes the independent collection service next.
    with transaction.atomic():
        # Same stable lock serializes imports even from different search queries.
        key = "import:" + str(ident)
        FetchLease.objects.get_or_create(
            key=key, defaults={"expires_at": timezone.now()}
        )
        FetchLease.objects.select_for_update().get(pk=key)
        ref = (
            ExternalRef.objects.filter(provider=api.PROVIDER, external_id=str(ident))
            .select_related("work")
            .first()
        )
        if ref:
            return ref.work
        fields = {
            key: item[key]
            for key in (
                "title",
                "kind",
                "year",
                "rating_kinopoisk",
                "rating_imdb",
                "poster_url",
            )
        }
        work = Work.objects.create(**fields)
        ExternalRef.objects.create(
            work=work,
            external_id=str(ident),
            fetched_at=fetched,
            expires_at=fetched + timedelta(days=30),
            source_type=item["source_type"],
        )
        return work
