from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def fetch_with_playwright(
    url: str,
    timeout: int = 15,  # seconds
    storage_state: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[str]:
    """
    Fetch fully-rendered HTML using Playwright (Chromium).

    Args:
        url: Target URL to fetch.
        timeout: Navigation timeout in seconds.
        storage_state: Optional path to Playwright storage state JSON (cookies/session). If provided, a logged-in context is used.
        user_agent: Optional custom User-Agent string.

    Returns:
        Page HTML (string) if success, otherwise None.
    """
    html = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context_kwargs = {}
        if storage_state:
            context_kwargs["storage_state"] = storage_state
        if user_agent:
            context_kwargs["user_agent"] = user_agent

        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        if user_agent:
            page.set_extra_http_headers({"Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"})
        try:
            # First stage: DOM content loaded
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            try:
                page.wait_for_selector("body", timeout=3000)
            except PlaywrightTimeoutError:
                pass
            # Second stage: try to reach network idle for fuller content
            try:
                page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            except PlaywrightTimeoutError:
                # It's okay if we don't reach full idle; use what we have.
                pass
            html = page.content()
        except Exception as e:
            print(f"[playwright] error: {e}")
            html = None
        finally:
            context.close()
            browser.close()
    return html

def resolve_final_url(url: str, timeout: int = 15, storage_state: Optional[str] = None, wait_until: str = "networkidle") -> Optional[str]:
    """
    以 Playwright 導航並回傳最終的 page.url（不取 HTML）。
    用於處理 facebook.com/share/r 類型的 JS 轉址。
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context_kwargs = {}
            if storage_state:
                context_kwargs["storage_state"] = storage_state
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            try:
                page.goto(url, wait_until=wait_until, timeout=timeout * 1000)
            except PlaywrightTimeoutError:
                # 即便超時也儘量回傳目前的 URL
                pass
            final = page.url
            context.close()
            browser.close()
            return final
    except Exception:
        return None