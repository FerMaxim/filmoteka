import sys

from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    response = page.goto(f"{sys.argv[1]}/health/ready")
    assert response.ok and response.json() == {"status": "ready"}
    browser.close()
