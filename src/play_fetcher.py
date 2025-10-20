from playwright.sync_api import sync_playwright
import time

def fetcher_with_playwright(uel):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        pages = browse.new_page()
        page.goto(url)
        
        time.sleep(2)
        
        html = page.content()
        
        browser.close()
        
        return html