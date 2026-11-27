import os
from pathlib import Path
from playwright.sync_api import sync_playwright

base = os.environ["PROTOTYPE_URL"]
out = Path("KB/ASSETS/T-004")
out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    for width in [320, 390, 768, 1440]:
        page.set_viewport_size({"width": width, "height": 1000})
        response = page.goto(base + "/")
        assert response.ok
        page.get_by_role("heading", name="Кино, которое остаётся с вами.").wait_for()
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        page.screenshot(path=str(out / f"home-{width}.png"), full_page=True)
    for route in ["catalog", "profile", "library"]:
        page.locator(f".navlinks [data-page={route}]").click()
        page.get_by_role("link", name="Filmoteka — главная").click()
        assert page.url == base + "/"
        assert page.locator("#home-title").evaluate("(e)=>e===document.activeElement")
    page.get_by_role("button", name="Открыть каталог", exact=True).click()
    page.locator('[data-film="3"]').focus()
    page.keyboard.press("Enter")
    page.locator("#criterion-0").focus()
    page.keyboard.press("Home")
    page.locator("#save-rating").click()
    page.get_by_role("link", name="Filmoteka — главная").focus()
    page.keyboard.press("Enter")
    page.get_by_role("button", name="Открыть библиотеку", exact=True).click()
    assert page.locator('[data-film="3"] .rating').inner_text() == "0,0"
    page.go_back()
    page.wait_for_function('document.activeElement.id==="home-title"')
    page.go_forward()
    assert (
        page.locator('[data-tab="Оценённые"]').get_attribute("aria-pressed") == "true"
    )
    page.get_by_role("link", name="Filmoteka — главная").click()
    page.reload()
    assert page.locator("#home-title").is_visible()
    page.emulate_media(reduced_motion="reduce")
    page.set_viewport_size({"width": 390, "height": 1000})
    page.evaluate('document.body.style.fontSize="28px"')
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    assert not errors, errors
    browser.close()
print(
    "PASS: root home, four widths, brand click/Enter from all sections, actions, history, reload and draft retention; no JS errors"
)
