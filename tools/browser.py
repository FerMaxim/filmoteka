import os
import secrets
import sys
from pathlib import Path

import django
from playwright.sync_api import sync_playwright

from filmoteka.test_postgresql.base import validate_target, verify_identity

marker, target = validate_target()
django.setup()
from django.db import connection  # noqa: E402
from django.core.exceptions import ImproperlyConfigured  # noqa: E402

if connection.settings_dict["ENGINE"] != "filmoteka.test_postgresql":
    raise ImproperlyConfigured("Browser checks require the guarded test backend")
with connection.cursor() as cursor:
    verify_identity(cursor, target["dbname"], target["user"], marker)

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from catalog.models import Work  # noqa: E402

url = sys.argv[1]
state = Path(sys.argv[2]) if len(sys.argv) > 2 else None
reopen = len(sys.argv) > 3 and sys.argv[3] == "reopen"
artifacts = Path(os.environ.get("FILMOTEKA_SCREENSHOTS", "test-results/T-008"))
artifacts.mkdir(parents=True, exist_ok=True)
if not reopen:
    call_command("seed_synthetic")
    password = secrets.token_urlsafe(24)
    user = get_user_model().objects.create_user(
        username="browser-alice", password=password
    )
    work = Work.objects.get(title="Синтетический маяк")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    context = browser.new_context(
        storage_state=str(state) if reopen else None, reduced_motion="reduce"
    )
    page = context.new_page()
    image_requests = []
    context.route(
        "https://st.kp.yandex.net/**",
        lambda route: (
            image_requests.append(route.request.url),
            route.fulfill(status=404, body=""),
        ),
    )
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    if reopen:
        page.goto(url + "/me/library/")
        assert page.get_by_role(
            "heading", name="Моя библиотека", exact=True
        ).is_visible()
        assert page.get_by_role(
            "heading", name="Синтетический маяк", exact=True
        ).is_visible()
        assert (
            page.get_by_role(
                "heading", name="Синтетический горизонт", exact=True
            ).count()
            == 1
        )
        print(
            "Library, imported catalog work and database session survived application restart"
        )
    else:
        for destination, button in [
            ("/catalog/", "Открыть каталог"),
            ("/me/library/", "Открыть библиотеку"),
        ]:
            context.clear_cookies()
            page.goto(url + "/")
            page.get_by_role("button", name=button, exact=True).click()
            assert "/accounts/login/" in page.url
            assert page.locator("input[name=next]").input_value() == destination
            page.get_by_label("Имя пользователя").fill(user.username)
            page.get_by_label("Пароль").fill(password)
            page.get_by_role("button", name="Войти", exact=True).click()
            page.wait_for_url(url + destination)
            page.get_by_role("link", name="Filmoteka", exact=True).click()
            page.wait_for_url(url + "/")
            page.go_back()
            page.wait_for_url(url + destination)
            page.go_forward()
            page.wait_for_url(url + "/")
        page.get_by_role("button", name="Открыть каталог", exact=True).click()
        page.wait_for_url(url + "/catalog/")
        page.get_by_label("Название произведения").fill("маяк")
        page.get_by_role("button", name="Найти", exact=True).click()
        page.get_by_role("heading", name="Синтетический маяк").get_by_role(
            "link"
        ).click()
        page.get_by_role("button", name="Добавить в библиотеку").click()
        page.reload()
        assert page.get_by_role("heading", name=work.title).count() == 1
        page.goto(url + f"/works/{work.pk}/")
        assert page.get_by_text("В вашей библиотеке", exact=True).is_visible()
        page.goto(url + "/me/library/")
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 960})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(
                path=str(artifacts / f"library-{width}.png"), full_page=True
            )
            page.goto(url + "/catalog/")
            page.screenshot(
                path=str(artifacts / f"catalog-{width}.png"), full_page=True
            )
            page.goto(url + "/me/library/")
        # The production UI uses the guarded test adapter: no live key or network.
        external_requests = []
        page.on(
            "request",
            lambda request: (
                external_requests.append(request.url)
                if "/catalog/external/" in request.url
                else None
            ),
        )
        page.goto(url + "/catalog/")
        page.get_by_label("Название произведения").fill("горизонт")
        page.wait_for_timeout(200)
        assert len(external_requests) == 0  # No search as the user types.
        page.get_by_label("Название произведения").press("Enter")
        page.locator("#external-results .server-work").first.wait_for()
        assert page.locator("#external-results .server-work").count() == 3
        assert len(external_requests) == 1
        assert page.get_by_text("Synthetic Original", exact=True).is_visible()
        assert page.get_by_text("Год не указан", exact=True).is_visible()
        assert page.locator(".external-ratings dt").filter(has_text="IMDb").count() == 3
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 960})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(artifacts / f"search-{width}.png"), full_page=True)
        page.get_by_role("link", name="Следующая страница Кинопоиска").click()
        page.locator("#external-results .server-work").first.wait_for()
        assert len(external_requests) == 2
        assert (
            page.get_by_role("link", name="Следующая страница Кинопоиска").count() == 0
        )
        page.goto(url + "/catalog/?q=горизонт")
        page.locator("#external-results .server-work").first.wait_for()
        page.locator("#external-results .server-work").first.get_by_role(
            "button", name="Добавить в библиотеку"
        ).click()
        page.get_by_role(
            "heading", name="Синтетический горизонт", exact=True
        ).wait_for()
        assert page.get_by_text("В вашей библиотеке", exact=True).is_visible()
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 960})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(
                path=str(artifacts / f"imported-{width}.png"), full_page=True
            )
        page.reload()
        assert page.get_by_text("В вашей библиотеке", exact=True).is_visible()
        page.goto(url + "/me/library/")
        page.get_by_role(
            "heading", name="Синтетический горизонт", exact=True
        ).wait_for()
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.tagName") in {
            "A",
            "BUTTON",
            "INPUT",
        }
        if state:
            context.storage_state(path=str(state))
        print(
            "Browser login, search, selection, add, reload and responsive checks passed"
        )
    assert not errors, errors
    browser.close()

if not reopen:
    from catalog.models import ProviderAttempt, ExternalRef

    assert (
        ProviderAttempt.objects.count() == 3
    )  # Empty local query + page 1 + explicit page 2.
    assert ExternalRef.objects.filter(external_id="9000001").count() == 1
    print(
        f"T-008: fixture API attempts=3; live JSON=0; intercepted image attempts={len(image_requests)}; live images=0"
    )
