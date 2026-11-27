import concurrent.futures
import threading
import time
from datetime import timedelta
from unittest.mock import Mock
import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, IntegrityError, transaction
from django.test import Client
from django.utils import timezone
from catalog import kinopoisk as api, provider
from catalog.models import (
    ExternalRef,
    FetchLease,
    ProviderAttempt,
    ProviderBudget,
    SearchCache,
    Work,
)
from collection.models import Entry
from tests.kinopoisk_fixtures import ITEMS, response

pytestmark = []


@pytest.fixture
def transport(monkeypatch):
    mock = Mock(side_effect=response)
    monkeypatch.setattr(api, "fetch", mock)
    return mock


@pytest.fixture
def user(client):
    user = get_user_model().objects.create_user(
        username="fixture-alice", password="synthetic-only"
    )
    client.force_login(user)
    return user


def reset_pause():
    ProviderBudget.objects.update(
        pause_until=timezone.now(), next_allowed_at=timezone.now()
    )


@pytest.mark.django_db
def test_search_cache_normalization_pages_and_costs(transport):
    payload, notice = provider.search("  СИНТЕТИЧЕСКИЙ   горизонт ")
    assert len(payload["items"]) == 3 and not notice
    assert transport.call_count == ProviderAttempt.objects.count() == 1
    assert provider.search("синтетический горизонт")[0] == payload
    assert transport.call_count == 1
    provider.search("синтетический горизонт", 2)
    assert transport.call_count == ProviderAttempt.objects.count() == 2
    assert transport.call_args.kwargs["page"] == 2
    cache = SearchCache.objects.get(pk=provider.cache_key("синтетический горизонт", 1))
    assert cache.expires_at - cache.fetched_at == timedelta(hours=24)
    provider.search("ничего")
    empty = SearchCache.objects.get(pk=provider.cache_key("ничего", 1))
    assert empty.expires_at - empty.fetched_at == timedelta(minutes=10)


@pytest.mark.django_db
def test_import_fresh_search_repeat_local_and_missing_fields(transport, client, user):
    query = "синтетический горизонт"
    provider.search(query)
    for ident in (9000001, 9000002, 9000003):
        for _ in range(2):
            result = client.post(
                "/catalog/import/",
                {"external_id": ident, "q": query, "external_page": 1},
            )
            assert result.status_code == 303
    assert transport.call_count == ProviderAttempt.objects.count() == 1
    assert (
        Work.objects.count()
        == ExternalRef.objects.count()
        == Entry.objects.count()
        == 3
    )
    assert Work.objects.filter(title="Синтетический горизонт").count() == 2
    fallback = Work.objects.get(title="Synthetic Original")
    assert (
        fallback.year is None
        and fallback.rating_imdb is None
        and not fallback.poster_url
    )
    assert fallback.kind == "other"
    assert all(
        e.added
        and not e.watched
        and not e.favorite
        and not e.want_to_watch
        and e.version == 2
        for e in Entry.objects.all()
    )
    # Stale source metadata never triggers an automatic refresh on local reads.
    SearchCache.objects.all().delete()
    ExternalRef.objects.update(expires_at=timezone.now() - timedelta(days=1))
    provider.import_work(9000001, query, 1)
    work = Work.objects.get(external_refs__external_id="9000001")
    assert client.get(f"/works/{work.pk}/").status_code == 200
    assert client.get("/me/library/").status_code == 200
    assert transport.call_count == 1


@pytest.mark.django_db
def test_import_fallback_one_details_call_and_rollback(transport):
    w = provider.import_work(9000001, "missing", 1)
    assert transport.call_count == 1
    assert transport.call_args.kwargs["ident"] == 9000001
    assert provider.import_work(9000001, "anything", 3) == w
    assert transport.call_count == 1
    with pytest.raises(api.Unavailable):
        provider.import_work(9000999, "missing", 1)
    assert Work.objects.count() == 1
    assert ExternalRef.objects.count() == 1


@pytest.mark.parametrize("status", [0, 401, 402, 403, 429, 500])
@pytest.mark.django_db
def test_errors_pause_and_rolling_budget(transport, settings, status):
    transport.side_effect = api.Unavailable(status)
    assert provider.search("query")[1]
    assert ProviderAttempt.objects.count() == transport.call_count == 1
    assert provider.search("another")[1]
    assert transport.call_count == 1
    reset_pause()
    transport.side_effect = response
    settings.KINOPOISK_REQUEST_BUDGET = 1
    assert provider.search("different")[1]
    assert transport.call_count == 1
    ProviderAttempt.objects.update(created_at=timezone.now() - timedelta(hours=25))
    reset_pause()
    assert not provider.search("синтетический горизонт")[1]
    assert transport.call_count == 2
    assert ProviderAttempt.objects.count() == 1


@pytest.mark.django_db
def test_stale_cache_survives_failure_and_disabled_does_not_call(transport, settings):
    payload, _ = provider.search("синтетический горизонт")
    SearchCache.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    transport.side_effect = api.Unavailable(429)
    stale, notice = provider.search("синтетический горизонт")
    assert stale["items"] == payload["items"] and notice
    settings.KINOPOISK_ENABLED = False
    assert provider.search("another")[1]
    assert transport.call_count == 2


@pytest.mark.django_db
def test_validation_auth_csrf_and_private_boundary(transport, client, user):
    guest = Client()
    assert guest.get("/catalog/external/?q=горизонт").status_code == 302
    assert guest.post("/catalog/import/", {"external_id": 9000001}).status_code == 302
    assert transport.call_count == 0
    # Local results respond without invoking the provider at all.
    assert client.get("/catalog/?q=горизонт").status_code == 200
    assert transport.call_count == 0
    assert client.get("/catalog/external/?q=" + "a" * 301).status_code == 422
    for page in ("0", "-1", "abc", "21"):
        assert (
            client.get(
                "/catalog/external/", {"q": "горизонт", "external_page": page}
            ).status_code
            == 422
        )
    assert transport.call_count == 0
    assert client.get("/catalog/import/").status_code == 405
    data = {"external_id": 9000001, "q": "горизонт", "external_page": 1}
    assert (
        client.post("/catalog/import/", {**data, "owner": user.pk + 1}).status_code
        == 422
    )
    for bad in (-1, 0, 15000001, "bad"):
        assert (
            client.post("/catalog/import/", {**data, "external_id": bad}).status_code
            == 422
        )
    secure = Client(enforce_csrf_checks=True)
    secure.force_login(user)
    assert secure.post("/catalog/import/", data).status_code == 403
    r = secure.get("/catalog/external/?q=горизонт")
    assert r.status_code == 200
    csrf = secure.cookies["csrftoken"].value
    assert (
        secure.post(
            "/catalog/import/", {**data, "csrfmiddlewaretoken": csrf}
        ).status_code
        == 303
    )
    other = get_user_model().objects.create_user(username="fixture-bob")
    client.force_login(other)
    assert "Синтетический горизонт" not in client.get("/me/library/").content.decode()
    assert client.post("/catalog/import/", data).status_code == 303
    assert Work.objects.count() == 1 and Entry.objects.count() == 2
    assert set(Entry.objects.values_list("owner_id", flat=True)) == {user.pk, other.pk}
    assert transport.call_count == 1
    remaining = client.get("/catalog/external/?q=горизонт").content.decode()
    assert 'value="9000001"' not in remaining
    assert 'value="9000002"' in remaining  # Same title is a different work.


@pytest.mark.quick
def test_nullable_mapping_and_safe_poster():
    result = api.candidate(
        {**ITEMS[0], "ratingKinopoisk": 0, "ratingImdb": 15, "year": "bad"}
    )
    assert (
        result["rating_kinopoisk"] == "0.0"
        and result["rating_imdb"] is None
        and result["year"] is None
    )
    assert (
        api.candidate({"kinopoiskId": 1, "nameEn": "Fallback"})["title"] == "Fallback"
    )
    assert api.candidate({"kinopoiskId": 1, "nameRu": " "}) is None
    for value in (
        None,
        "javascript:alert(1)",
        "https://localhost/a",
        "https://st.kp.yandex.net:bad/a",
        "https://user@st.kp.yandex.net/a",
        "https://[invalid",
    ):
        assert api.poster_url(value) == ""
    assert (
        api.normalize_response(
            {"items": [ITEMS[0], ITEMS[0], ITEMS[1]], "totalPages": 1}
        )["items"][1]["external_id"]
        == "9000002"
    )
    with pytest.raises(api.Unavailable):
        api.normalize_response({"items": "invalid"})


@pytest.mark.django_db(transaction=True)
def test_concurrent_search_and_import_single_request(monkeypatch):
    lock = threading.Lock()
    count = 0

    def slow(**kwargs):
        nonlocal count
        with lock:
            count += 1
        time.sleep(0.15)
        return response(**kwargs)

    monkeypatch.setattr(api, "fetch", slow)

    def run_concurrent(action):
        gate = threading.Barrier(2)

        def worker():
            close_old_connections()
            try:
                gate.wait(timeout=10)
                return action()
            finally:
                close_old_connections()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker) for _ in range(2)]
            return [f.result(timeout=15) for f in futures]

    payloads = run_concurrent(lambda: provider.search("горизонт"))
    assert payloads[0] == payloads[1] and count == 1
    ids = run_concurrent(lambda: provider.import_work(9000001, "горизонт", 1).pk)
    assert ids[0] == ids[1] and count == 1
    # No search-cache entry: two importers still share one details call.
    ids = run_concurrent(lambda: provider.import_work(9000002, "missing", 1).pk)
    assert ids[0] == ids[1] and count == 2
    assert Work.objects.count() == ExternalRef.objects.count() == 2
    assert ProviderAttempt.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_budget_reservation_is_atomic(settings):
    settings.KINOPOISK_REQUEST_BUDGET = 1
    gate = threading.Barrier(2)

    def worker():
        close_old_connections()
        try:
            gate.wait(timeout=10)
            try:
                provider.reserve()
                return True
            except api.Unavailable:
                return False
        finally:
            close_old_connections()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: worker(), range(2)))
    assert sorted(results) == [False, True]
    assert ProviderAttempt.objects.count() == 1


@pytest.mark.django_db
def test_database_constraints_and_stale_owner_fencing(transport):
    work = Work.objects.create(title="fixture", kind="film")
    for fields in ({"year": 1700}, {"rating_imdb": 11}, {"rating_kinopoisk": -1}):
        with pytest.raises(IntegrityError), transaction.atomic():
            Work.objects.filter(pk=work.pk).update(**fields)
    key = provider.cache_key("горизонт", 1)

    def stolen(**kwargs):
        FetchLease.objects.filter(pk=key).update(token=None)
        return response(**kwargs)

    transport.side_effect = stolen
    assert provider.search("горизонт")[1]
    assert not SearchCache.objects.filter(pk=key).exists()


@pytest.mark.quick
def test_adapter_http_boundary_without_network(monkeypatch, settings):
    from io import BytesIO
    from urllib.error import HTTPError

    settings.KINOPOISK_ENABLED = True
    settings.KINOPOISK_DATA_APPROVED = True
    settings.KINOPOISK_API_KEY = "synthetic-header-only"
    settings.KINOPOISK_TEST_FIXTURES = False
    opener = Mock()
    opener.open.return_value = BytesIO(b'{"items": [], "totalPages": 0}')
    monkeypatch.setattr(api, "build_opener", Mock(return_value=opener))
    assert api.fetch(query="Название & keyword=other", page=2)["items"] == []
    request = opener.open.call_args.args[0]
    assert request.full_url.startswith(api.BASE + "?keyword=")
    assert "synthetic-header-only" not in request.full_url
    assert request.get_header("X-api-key") == "synthetic-header-only"
    assert "&page=2" in request.full_url and "%26" in request.full_url
    assert opener.open.call_args.kwargs == {"timeout": 4}
    assert api.NoRedirect().redirect_request(None, None, None, None, None, None) is None
    opener.open.side_effect = HTTPError(api.BASE, 429, "limited", {}, None)
    with pytest.raises(api.Unavailable) as error:
        api.fetch(ident=9000001)
    assert error.value.status == 429
    settings.KINOPOISK_ENABLED = False
    opener.open.reset_mock()
    with pytest.raises(api.Unavailable):
        api.fetch(query="disabled")
    opener.open.assert_not_called()


@pytest.mark.django_db
def test_expired_lease_recovery_and_pause_never_shortens(transport):
    key = provider.cache_key("горизонт", 1)
    FetchLease.objects.create(key=key, expires_at=timezone.now() - timedelta(seconds=1))
    assert not provider.search("горизонт")[1]
    provider.pause(402)
    previous = ProviderBudget.objects.get(pk=api.scope()).pause_until
    provider.pause(500)
    assert ProviderBudget.objects.get(pk=api.scope()).pause_until == previous
    assert provider.search("a second query")[1]
    assert transport.call_count == 1
