import os
from pathlib import Path
from playwright.sync_api import sync_playwright

url = os.environ["PROTOTYPE_URL"] + "/prototype/"
ref = Path("KB/ASSETS/DESIGN/SVET-04/Filmoteka_Svet_FINAL.html").resolve().as_uri()
out = Path("KB/ASSETS/T-003/svet")
out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    for width in [320, 390, 768, 1280, 1440]:
        page.set_viewport_size({"width": width, "height": 1000})
        for source, link in [("reference", ref), ("implementation", url)]:
            page.goto(link)
            if source == "reference":
                page.add_style_tag(content=".lab{display:none}")
            page.wait_for_timeout(900)
            for state in ["profile", "hover", "modal", "catalog"]:
                if state == "hover":
                    page.locator("[data-film]").first.hover()
                    page.wait_for_timeout(450)
                if state == "modal":
                    page.locator("[data-film]").first.click()
                    page.wait_for_timeout(350)
                if state == "catalog":
                    page.keyboard.press("Escape")
                    page.locator("[data-page=catalog]").click()
                    page.wait_for_timeout(350)
                page.screenshot(
                    path=str(out / f"{source}-{state}-{width}.png"), full_page=True
                )
                assert page.evaluate(
                    "document.documentElement.scrollWidth<=innerWidth"
                ), (source, state, width)
            page.locator("[data-page=profile]").first.click()
            if width in [390, 1440]:
                for name in [
                    "Рекомендации",
                    "Оценённые",
                    "Избранное",
                    "Хочу посмотреть",
                    "Просмотрено",
                ]:
                    page.locator(f'[data-tab="{name}"]').click()
                    page.wait_for_timeout(900)
                    page.screenshot(
                        path=str(out / f"{source}-tab-{name}-{width}.png"),
                        full_page=True,
                    )
            page.locator(".name-row h1").evaluate(
                '(e)=>e.textContent="ОченьДлинныйНикБезПробеловДляПроверкиКириллицы"'
            )
            page.locator(".film-info h3").first.evaluate(
                '(e)=>e.textContent="Очень длинное название произведения для проверки переноса кириллицы"'
            )
            page.wait_for_timeout(900)
            page.screenshot(
                path=str(out / f"{source}-long-{width}.png"), full_page=True
            )
    page.goto(url)
    for tab in [
        "Рекомендации",
        "Оценённые",
        "Избранное",
        "Хочу посмотреть",
        "Просмотрено",
    ]:
        page.locator(f'[data-tab="{tab}"]').click()
        page.wait_for_timeout(900)
        page.screenshot(path=str(out / f"tab-{tab}.png"), full_page=True)
    page.locator("[data-page=catalog]").click()
    page.locator('[data-film="3"]').focus()
    page.keyboard.press("Enter")
    assert page.locator("dialog").evaluate("(e)=>e.open")
    page.keyboard.press("Shift+Tab")
    assert page.locator("dialog").evaluate("(e)=>e.contains(document.activeElement)")
    page.keyboard.press("Tab")
    assert page.locator("dialog").evaluate("(e)=>e.contains(document.activeElement)")
    page.locator("#save-rating").click()
    assert page.locator("#criterion-0").get_attribute("aria-invalid") == "true"
    page.screenshot(path=str(out / "error-1440.png"), full_page=True)

    def score(i, v):
        page.locator(f"#criterion-{i}").evaluate(
            '(e,v)=>{e.value=v;e.dispatchEvent(new Event("input",{bubbles:true}))}',
            str(v),
        )

    score(0, 0)
    assert page.locator("#score").inner_text() == "0,0"
    score(0, 8)
    score(1, 0)
    assert page.locator("#score").inner_text() == "4,0"
    score(2, 10)
    assert page.locator("#score").inner_text() == "6,5"
    page.get_by_label("Очистить: Сюжет", exact=True).click()
    assert page.locator("#score").inner_text() == "9,0"
    score(1, 0)
    # Range constrains user input to its domain, including keyboard End/Home.
    page.locator("#criterion-1").focus()
    page.keyboard.press("End")
    assert page.locator("#criterion-1").input_value() == "10"
    page.keyboard.press("Home")
    assert page.locator("#criterion-1").input_value() == "0"
    page.locator('[data-emotion="Радость"]').click()
    page.locator("#comment").fill("Синтетический комментарий")
    page.locator("#save-rating").focus()
    page.keyboard.press("Enter")
    assert not page.locator("dialog").evaluate("(e)=>e.open")
    assert page.locator('[data-film="3"]').evaluate("(e)=>e===document.activeElement")
    page.keyboard.press("Enter")
    assert page.locator("#comment").input_value() == "Синтетический комментарий"
    assert (
        page.locator('[data-emotion="Радость"]').get_attribute("aria-pressed") == "true"
    )
    assert page.locator("#score").inner_text() == "6,5"
    page.locator("[data-action=delete-rec]").click()
    page.keyboard.press("Enter")
    assert page.locator("#score").inner_text() == "6,5"
    assert page.locator("#recommendation").input_value() == ""
    page.locator("#recommendation").fill("Отдельный совет")
    page.locator("[data-action=save-rec]").click()
    page.keyboard.press("Enter")
    assert page.locator("#recommendation").input_value() == "Отдельный совет"
    page.keyboard.press("Escape")
    assert page.locator('[data-film="3"]').evaluate("(e)=>e===document.activeElement")
    page.locator("#q").fill("нет такого названия")
    assert page.locator(".empty").is_visible()
    page.screenshot(path=str(out / "empty.png"), full_page=True)
    page.locator("[data-page=profile]").first.click()
    default = page.locator(".base-scene").evaluate(
        "(e)=>getComputedStyle(e).backgroundImage"
    )
    page.locator("[data-film]").first.hover()
    assert (
        page.locator(".base-scene").evaluate("(e)=>getComputedStyle(e).backgroundImage")
        == default
    )
    # Valid local fixture, no upload to server.
    page.locator("#background-file").set_input_files(
        "KB/ASSETS/DESIGN/SVET-04/PROFILE_PREVIEW.png"
    )
    page.locator(".base-scene.photo").wait_for()
    page.screenshot(path=str(out / "custom-photo.png"), full_page=True)
    page.locator("[data-action=reset-bg]").click()
    assert (
        page.locator(".base-scene").evaluate("(e)=>getComputedStyle(e).backgroundImage")
        == default
    )
    page.locator("#background-file").set_input_files(
        {"name": "bad.png", "mimeType": "image/png", "buffer": b"not an image"}
    )
    page.get_by_text("Не удалось прочитать изображение", exact=True).wait_for()
    page.locator(".name-row h1").evaluate(
        '(e)=>e.textContent="ОченьДлинныйНикБезПробеловДляПроверкиКириллицы"'
    )
    for width in [320, 390, 768, 1280, 1440]:
        page.set_viewport_size({"width": width, "height": 1000})
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    page.emulate_media(reduced_motion="reduce")
    for route in ["profile", "catalog"]:
        page.locator(f"[data-page={route}]").first.click()
        page.set_viewport_size({"width": 390, "height": 1000})
        page.evaluate('document.body.style.fontSize="28px"')
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        page.screenshot(path=str(out / f"large-reduced-{route}.png"), full_page=True)
    page.locator("[data-film]").first.focus()
    page.keyboard.press("Enter")
    assert page.locator(".modal").evaluate("(e)=>e.scrollWidth<=e.clientWidth")
    page.screenshot(path=str(out / "large-reduced-modal.png"), full_page=True)
    touch = browser.new_context(
        has_touch=True, is_mobile=True, viewport={"width": 390, "height": 1000}
    )
    t = touch.new_page()
    t.goto(url)
    t.locator("[data-open]").first.tap()
    assert t.locator("dialog").evaluate("(e)=>e.open")
    touch.close()
    assert not errors, errors
    browser.close()
print(
    "PASS: Svet comparisons at five widths, tabs, modal keyboard, formula/zero/omission/range, emotion/comment/recommendation independence, photo reset/invalid image, long name, reduced motion, touch; no JS errors"
)
