from .classifier import classify
from .fetcher import fetch_html
from .parser import parse_basic_meta
import time

def inspect_url(url: str) -> dict:
    """
    Inspect a social URL: classify -> (optional rewrite) -> fetch -> parse.

    - Rewrites www.facebook.com to m.facebook.com for better unauthenticated access.
    - Returns a stable schema with meta diagnostics.
    """
    t0 = time.time()
    type_tag = classify(url)

    # Normalize FB URLs to mobile version to avoid login wall
    was_rewritten = False
    rewritten_url = url
    if type_tag in ("fb_page", "fb_post", "fb_group"):
        if "m.facebook.com" not in url:
            rewritten_url = (
                url.replace("https://www.facebook.com", "https://m.facebook.com")
                   .replace("http://www.facebook.com", "http://m.facebook.com")
                   .replace("https://facebook.com", "https://m.facebook.com")
                   .replace("http://facebook.com", "http://m.facebook.com")
            )
            was_rewritten = (rewritten_url != url)
            
        if "facebook.com" in url and "m.facebook.com" not in url:
            url = url.replace("www.facebook.com", "m.facebook.com").replace("facebook.com", "m.facebook.com")

    html = fetch_html(rewritten_url)

    if not html:
        return {
            "status": "error",
            "type": type_tag,
            "data": None,
            "meta": {
                "duration_ms": int((time.time() - t0) * 1000),
                "fetched_with": "requests",
                "was_rewritten": was_rewritten,
                "rewritten_url": rewritten_url if was_rewritten else None,
            },
            "error": "fetch_failed",
        }

    data = parse_basic_meta(html)

    tag_to_kind = {
        "fb_page": "page",
        "fb_post": "post",
        "fb_group": "group",
        "ig_profile": "profile",
        "ig_post": "post",
    }
    data["kind"] = tag_to_kind.get(type_tag, "unknown")

    return {
        "status": "ok",
        "type": type_tag,
        "data": data,
        "meta": {
            "duration_ms": int((time.time() - t0) * 1000),
            "fetched_with": "requests",
            "was_rewritten": was_rewritten,
            "rewritten_url": rewritten_url if was_rewritten else None,
        },
        "error": None,
    }