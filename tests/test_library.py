import concurrent.futures
import threading
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client
from catalog.models import Work
from collection.models import Entry
from collection.services import add_to_library

pytestmark = pytest.mark.django_db


@pytest.fixture
def data():
    a = get_user_model().objects.create_user(
        username="alice", password="synthetic-test-only"
    )
    b = get_user_model().objects.create_user(
        username="bob", password="synthetic-test-only"
    )
    w = Work.objects.create(title="Синтетический маяк", kind="film")
    return a, b, w


def test_session_path_and_owner_validation(data):
    a, b, w = data
    client = Client(enforce_csrf_checks=True)
    assert client.get("/me/library/").status_code == 302
    assert (
        client.post(f"/me/works/{w.pk}/library/", {"added": "true"}).status_code == 403
    )
    client.get("/accounts/login/")
    csrf = client.cookies["csrftoken"].value
    old_session = client.session.session_key
    r = client.post(
        "/accounts/login/",
        {
            "username": "alice",
            "password": "synthetic-test-only",
            "csrfmiddlewaretoken": csrf,
        },
    )
    assert r.status_code == 303
    assert client.session.session_key != old_session
    csrf = client.cookies["csrftoken"].value
    assert client.get("/catalog/?q=маяк").status_code == 200
    assert client.get(f"/works/{w.pk}/").status_code == 200
    url = f"/me/works/{w.pk}/library/"
    assert client.get(url).status_code == 405
    assert client.post(url, {"added": "true"}).status_code == 403
    for bad in [
        {"owner": b.pk, "added": "true"},
        {"added": "false"},
        {"favorite": "true"},
        {"entry_id": 1, "added": "true"},
    ]:
        assert client.post(url, {**bad, "csrfmiddlewaretoken": csrf}).status_code == 422
    for _ in range(2):
        assert (
            client.post(url, {"added": "true", "csrfmiddlewaretoken": csrf}).status_code
            == 303
        )
    e = Entry.objects.get(owner=a, work=w)
    assert e.added and not any([e.favorite, e.watched, e.want_to_watch])
    assert e.version == 2
    assert Entry.objects.count() == 1
    assert w.title in client.get("/me/library/").content.decode()
    other_session = Client()
    other_session.force_login(b)
    assert w.title not in other_session.get("/me/library/").content.decode()
    assert other_session.get(f"/me/entries/{e.pk}/").status_code == 404
    assert (
        other_session.post(f"/me/entries/{e.pk}/", {"added": "false"}).status_code
        == 404
    )
    assert other_session.post(url, {"added": "true", "owner": a.pk}).status_code == 422
    assert other_session.post(url, {"added": "true"}).status_code == 303
    assert Entry.objects.count() == 2
    e.refresh_from_db()
    assert e.added and e.owner == a
    assert client.get("/accounts/logout/").status_code == 405
    assert (
        client.post("/accounts/logout/", {"csrfmiddlewaretoken": csrf}).status_code
        == 303
    )
    assert client.get("/me/library/").status_code == 302
    guest = Client()
    assert guest.post(url, {"added": "true"}).status_code == 302


def test_constraints_flags_and_rollback(data):
    a, b, w = data
    e = Entry.objects.create(owner=a, work=w, favorite=True, watched=True)
    assert not e.added and not e.want_to_watch
    add_to_library(owner=a, work=w)
    e.refresh_from_db()
    assert e.favorite and e.watched and e.added
    with pytest.raises(IntegrityError), transaction.atomic():
        Entry.objects.create(owner=a, work=w)
    with pytest.raises(IntegrityError), transaction.atomic():
        Entry.objects.create(owner=b, work=w, version=0)
    with pytest.raises(RuntimeError), transaction.atomic():
        add_to_library(owner=b, work=w)
        raise RuntimeError("rollback")
    assert not Entry.objects.filter(owner=b).exists()
    for values in [
        {"title": "", "kind": "film"},
        {"title": "invalid", "kind": "unknown"},
    ]:
        with pytest.raises(IntegrityError), transaction.atomic():
            Work.objects.create(**values)


def test_search_validation_and_private_reads(data, client):
    a, _, w = data
    client.force_login(a)
    assert client.get("/catalog/?q=" + "a" * 301).status_code == 422
    assert client.get("/works/999999/").status_code == 404
    assert (
        client.post("/me/works/999999/library/", {"added": "true"}).status_code == 404
    )
    assert Entry.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_add_uses_separate_connections(data):
    a, _, w = data
    gate = threading.Barrier(2)

    def add():
        close_old_connections()
        try:
            gate.wait(timeout=10)
            return add_to_library(owner=a, work=w).pk
        finally:
            close_old_connections()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(add) for _ in range(2)]
        ids = [f.result(timeout=20) for f in futures]
    assert ids[0] == ids[1]
    assert Entry.objects.get(owner=a, work=w).version == 2
