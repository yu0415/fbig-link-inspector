from typing import Optional
from playwright.sync_api import sync_playwright


def fetch_with_playwright(
    url: str,
    timeout: int = 15,  # seconds
    storage_state: Optional[str] = None,
) -> Optional[str]:
    """
    Fetch fully-rendered HTML using Playwright (Chromium).

    Args:
        url: target URL to fetch.
        timeout: navigation timeout in seconds.
        storage_state: optional path to Playwright storage state JSON (cookies/session).

    Returns:
        The page HTML (string) if success, otherwise None.
    """
    html = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context_kwargs = {}
        if storage_state:
            context_kwargs["storage_state"] = storage_state
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            html = page.content()
        except Exception as e:
            print(f"[playwright] error: {e}")
            html = None
        finally:
            context.close()
            browser.close()
    return html