from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    response = page.goto("http://web:8000/health/ready")
    assert response.ok and response.json() == {"status": "ready"}
    browser.close()
