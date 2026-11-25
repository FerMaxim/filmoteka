import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path("KB/ASSETS/T-003")
url = os.environ["PROTOTYPE_URL"] + "/prototype/"
report = {}
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 950})
    page.goto(url + "#catalog")
    page.get_by_role("button", name="Оценить", exact=True).first.focus()
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement.id === 'work-title'")
    page.screenshot(path=str(out / "focus-rating-390.png"), full_page=True)
    page.keyboard.press("Tab")
    assert page.get_by_label("Общее впечатление", exact=True).evaluate(
        "(e)=>e===document.activeElement"
    )
    page.keyboard.type("8")
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    assert page.get_by_label("Сюжет", exact=True).evaluate(
        "(e)=>e===document.activeElement"
    )
    page.keyboard.type("11")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Space")
    assert not page.locator("details").evaluate("(e)=>e.open")
    for _ in range(7):
        page.keyboard.press("Tab")
    assert page.get_by_role("button", name="Сохранить оценку").evaluate(
        "(e)=>e===document.activeElement"
    )
    page.keyboard.press("Enter")
    assert page.locator("details").evaluate("(e)=>e.open")
    assert page.get_by_label("Сюжет", exact=True).evaluate(
        "(e)=>e===document.activeElement"
    )
    assert (
        page.get_by_label("Сюжет", exact=True).get_attribute("aria-describedby")
        == "form-status"
    )
    page.screenshot(path=str(out / "error-focus-390.png"), full_page=True)
    page.keyboard.press("Control+A")
    page.keyboard.type("7")
    for _ in range(13):
        page.keyboard.press("Tab")
    assert page.get_by_role("button", name="Сохранить оценку").evaluate(
        "(e)=>e===document.activeElement"
    )
    page.keyboard.press("Enter")
    assert "сохранена" in page.locator("#form-status").inner_text()
    # Return via header links, then reach rated tab without direct DOM focus.
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement.matches('#profile h1')")
    for _ in range(3):
        page.keyboard.press("Tab")
    assert page.get_by_role("button", name="Оценённое", exact=True).evaluate(
        "(e)=>e===document.activeElement"
    )
    page.keyboard.press("Enter")
    assert page.get_by_text("Моя оценка: 7.5").is_visible()
    report["keyboard_regression"] = (
        "PASS: catalog Enter -> title -> input; collapsed invalid criterion -> open, described, focused; correction -> save -> profile -> rated"
    )
    report["tab_order"] = {}
    for route in ["profile", "catalog", "rating"]:
        page.goto("about:blank")
        page.goto(url + "#" + route)
        order = []
        for _ in range(35):
            page.keyboard.press("Tab")
            entry = page.evaluate(
                """()=>{const e=document.activeElement;return {tag:e.tagName,name:e.labels?.[0]?.textContent.trim()||e.textContent.trim().slice(0,65),visible:!!e.getClientRects().length,hidden:!!e.closest('[hidden]')}}"""
            )
            if entry["tag"] == "BODY":
                continue  # Browser chrome boundary at the end of tab order.
            assert entry["visible"] and not entry["hidden"], entry
            order.append(entry)
        report["tab_order"][route] = order
        page.emulate_media(reduced_motion="reduce")
        page.evaluate("document.documentElement.style.fontSize='32px'")
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), route
        page.screenshot(
            path=str(out / f"{route}-large-reduced-390.png"), full_page=True
        )
        assert (
            page.locator("button").first.evaluate(
                "(e)=>getComputedStyle(e).transitionDuration"
            )
            == "0s"
        )
    # Cold context per route; CDP network throttling, fourfold CPU slowdown.
    report["performance"] = {}
    for route in ["profile", "catalog", "rating"]:
        context = browser.new_context(viewport={"width": 390, "height": 950})
        perf = context.new_page()
        cdp = context.new_cdp_session(perf)
        cdp.send("Network.enable")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        cdp.send(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": 150,
                "downloadThroughput": 200000,
                "uploadThroughput": 93750,
            },
        )
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        perf.add_init_script(
            """window.vitals={lcp:0,cls:0};new PerformanceObserver(l=>{for(const e of l.getEntries())window.vitals.lcp=e.startTime}).observe({type:'largest-contentful-paint',buffered:true});new PerformanceObserver(l=>{for(const e of l.getEntries())if(!e.hadRecentInput)window.vitals.cls+=e.value}).observe({type:'layout-shift',buffered:true});"""
        )
        perf.goto(url + "#" + route)
        perf.wait_for_timeout(2500)
        report["performance"][route] = perf.evaluate(
            """()=>({...window.vitals,resources:performance.getEntriesByType('resource').map(e=>({name:e.name.split('/').pop(),bytes:e.encodedBodySize})),imageBytes:0})"""
        )
        context.close()
    browser.close()


# WCAG relative luminance calculation for solid backgrounds.
def luminance(color):
    values = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return sum(
        (v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) * w
        for v, w in zip(values, [0.2126, 0.7152, 0.0722])
    )


def contrast(a, b):
    x, y = sorted([luminance(a), luminance(b)])
    return round((y + 0.05) / (x + 0.05), 2)


report["contrast"] = {
    "fieldBorder/field": contrast("#79849b", "#242b39"),
    "focus/field": contrast("#f4d69b", "#242b39"),
}
assert report["contrast"]["fieldBorder/field"] >= 3
for name, a, b in [
    ("text/background", "#f0eef6", "#171b25"),
    ("muted/background", "#b5bdcf", "#171b25"),
    ("placeholder/field", "#b5bdcf", "#242b39"),
    ("text/field", "#f0eef6", "#242b39"),
    ("primary", "#171b25", "#c8b9ed"),
    ("error/background", "#f4d69b", "#171b25"),
]:
    value = contrast(a, b)
    assert value >= 4.5
    report["contrast"][name] = value
(out / "accessibility.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    "PASS: keyboard regression, 35 Tab presses per screen, enlarged text/reduced motion all screens, contrast and throttled metrics recorded"
)
