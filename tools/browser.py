import os
import secrets
import sys
from pathlib import Path

import django
from playwright.sync_api import sync_playwright

django.setup()
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from catalog.models import Work  # noqa: E402

url = sys.argv[1]
state = Path(sys.argv[2]) if len(sys.argv) > 2 else None
reopen = len(sys.argv) > 3 and sys.argv[3] == "reopen"
artifacts = Path(os.environ.get("FILMOTEKA_SCREENSHOTS", "test-results/T-005"))
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
        print("Library and database session survived application restart")
    else:
        page.goto(url + "/me/library/")
        assert "/accounts/login/" in page.url
        page.get_by_label("Имя пользователя").fill(user.username)
        page.get_by_label("Пароль").fill(password)
        page.get_by_role("button", name="Войти", exact=True).click()
        page.get_by_role("link", name="Каталог", exact=True).click()
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
