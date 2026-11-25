from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    for width in [390, 1440]:
        page.set_viewport_size({"width": width, "height": 950})
        for route in ["profile", "catalog", "rating"]:
            page.goto("about:blank")
            page.goto("http://127.0.0.1:8025/prototype/#" + route)
            page.screenshot(path=f"KB/ASSETS/T-003/{route}-{width}.png", full_page=True)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), (route, width)
        page.goto("about:blank")
        page.goto("http://127.0.0.1:8025/prototype/#profile")
        page.get_by_role("button", name="Скрыть сцену").click()
        page.screenshot(path=f"KB/ASSETS/T-003/fallback-{width}.png", full_page=True)
    page.goto("http://127.0.0.1:8025/prototype/#catalog")
    page.get_by_role("searchbox").fill("несуществующее")
    assert page.get_by_text("Ничего не найдено.", exact=False).is_visible()
    page.goto("http://127.0.0.1:8025/prototype/#rating")
    page.get_by_role("button", name="Сохранить оценку").click()
    assert page.get_by_text("Укажите общее впечатление", exact=False).is_visible()
    page.get_by_label("Общее впечатление", exact=True).fill("0")
    assert page.locator("#total").inner_text() == "0.0"
    page.get_by_label("Общее впечатление", exact=True).fill("8")
    page.get_by_label("Сюжет", exact=True).fill("0")
    assert page.locator("#total").inner_text() == "4.0"
    page.get_by_label("Персонажи", exact=True).fill("10")
    assert page.locator("#total").inner_text() == "6.5"
    page.get_by_label("Сюжет", exact=True).fill("11")
    assert page.locator("#total").inner_text() == "—"
    page.get_by_label("Сюжет", exact=True).fill("0")
    page.get_by_label("Радость", exact=True).check()
    page.get_by_label("Комментарий", exact=True).fill("Синтетический комментарий")
    page.get_by_role("button", name="Сохранить оценку").focus()
    page.keyboard.press("Enter")
    assert page.get_by_text(
        "Оценка сохранена до перезагрузки.", exact=False
    ).is_visible()
    page.goto("http://127.0.0.1:8025/prototype/#profile")
    page.get_by_role("button", name="Оценённое", exact=True).click()
    assert page.get_by_text("Моя оценка: 6.5").is_visible()
    page.emulate_media(reduced_motion="reduce")
    page.set_viewport_size({"width": 780, "height": 950})
    page.evaluate("document.documentElement.style.fontSize='32px'")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors, errors
    browser.close()
print(
    "PASS: 8 screenshots; responsive overflow; search empty; required/range/zero/partial calculation; keyboard save and rated tab; reduced motion + enlarged text; no JS errors"
)
