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
    # Real home destinations require a session; the prototype runner uses no DB.
    for route, destination in [("catalog", "/catalog/"), ("library", "/me/library/")]:
        page.goto(base + "/")
        page.locator(f".navlinks [data-page={route}]").click()
        page.wait_for_url("**/accounts/login/**")
        assert page.locator("input[name=next]").input_value() == destination
        page.get_by_role("link", name="Filmoteka", exact=True).click()
        page.wait_for_url(base + "/")
        page.go_back()
        page.wait_for_url("**/accounts/login/**")
        page.go_forward()
        page.wait_for_url(base + "/")
    # Temporary rating state belongs to the explicit demonstration route.
    page.goto(base + "/prototype/?view=catalog")
    page.locator('[data-film="3"]').focus()
    page.keyboard.press("Enter")
    page.locator("#criterion-0").focus()
    page.keyboard.press("Home")
    page.locator("#save-rating").click()
    page.locator(".navlinks [data-page=library]").click()
    assert page.locator('[data-film="3"] .rating').inner_text() == "0,0"
    page.get_by_role("link", name="Filmoteka — главная").focus()
    page.keyboard.press("Enter")
    assert page.locator("#home-title").evaluate("(e)=>e===document.activeElement")
    page.go_back()
    page.locator('[data-tab="Оценённые"]').wait_for()
    assert page.locator('[data-film="3"] .rating').inner_text() == "0,0"
    page.go_forward()
    page.locator("#home-title").wait_for()
    page.reload()
    assert page.locator("#home-title").is_visible()
    page.emulate_media(reduced_motion="reduce")
    page.set_viewport_size({"width": 390, "height": 1000})
    page.evaluate('document.body.style.fontSize="28px"')
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    assert not errors, errors
    browser.close()
print(
    "PASS: root home, four widths, protected destinations, brand, history, reload and prototype draft retention; no JS errors"
)
