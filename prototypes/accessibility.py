import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path("KB/ASSETS/T-003/svet")
url = os.environ["PROTOTYPE_URL"] + "/prototype/"
report = {}
with sync_playwright() as p:
    browser = p.chromium.launch()
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
        perf.goto(url + "?view=" + route)
        perf.wait_for_timeout(2500)
        report["performance"][route] = perf.evaluate(
            """()=>({...window.vitals,resources:performance.getEntriesByType('resource').map(e=>({name:e.name.split('/').pop(),bytes:e.encodedBodySize})),imageBytes:performance.getEntriesByType('resource').filter(e=>/art-/.test(e.name)).reduce((s,e)=>s+e.encodedBodySize,0)})"""
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
    "fieldBorder/field": contrast("#79849b", "#201e2a"),
    "focus/field": contrast("#dbb687", "#201e2a"),
}
assert report["contrast"]["fieldBorder/field"] >= 3
for name, a, b in [
    ("text/background", "#f2f0ea", "#111016"),
    ("muted/background", "#a6acb0", "#111016"),
    ("placeholder/field", "#b7bdc5", "#201e2a"),
    ("text/field", "#f2f0ea", "#201e2a"),
    ("primary", "#111016", "#d7c2f0"),
    ("error/background", "#dbb687", "#111016"),
]:
    value = contrast(a, b)
    assert value >= 4.5
    report["contrast"][name] = value
(out / "accessibility.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("PASS: Svet contrast and throttled metrics recorded")
