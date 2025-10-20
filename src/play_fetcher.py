from playwright.sync_api import sync_playwright
import time

def fetch_with_playwright(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        time.sleep(2)
        html = page.content()
        browser.close()
        return html