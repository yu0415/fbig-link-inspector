from .classifier import classify
from .fetcher import fetch_html
from .parser import (
    parse_fb_page_basic, parse_fb_post_basic,
    parse_fb_group_basic, parse_fb_group_post_basic,
    parse_ig_profile_basic, parse_ig_post_basic
)
import os
import time
from typing import Dict, Any

def _format_basic_zh(kind: str, basic: Dict[str, Any]) -> Dict[str, Any]:
    """
    將 internal basic 欄位轉換為中文「基礎資訊」欄位。
    只輸出需求列的欄位，並附加「數據來源」「備註」。
    """
    basic = basic or {}
    zh: Dict[str, Any] = {}
    if kind == "fb_page":
        zh["粉絲專頁追蹤數"] = basic.get("followers")
    elif kind == "fb_post":
        zh["貼文按讚數"] = basic.get("likes")
        zh["貼文分享數"] = basic.get("shares")
        zh["貼文所屬粉絲專頁追蹤數"] = basic.get("page_followers")
    elif kind == "fb_group":
        zh["社團成員數"] = basic.get("members")
    elif kind == "fb_group_post":
        zh["貼文按讚數"] = basic.get("likes")
        zh["貼文分享數"] = basic.get("shares")
        zh["貼文所屬社團成員數"] = basic.get("group_members")
    elif kind == "ig_profile":
        zh["帳號追蹤數"] = basic.get("followers")
    elif kind == "ig_post":
        zh["貼文按讚數"] = basic.get("likes")
        zh["貼文所屬帳號追蹤數"] = basic.get("owner_followers")
    zh["數據來源"] = basic.get("source_hint")
    zh["備註"] = basic.get("note")
    return zh

def inspect_url(url: str) -> dict:
    """
    Inspect a social URL: classify -> (optional rewrite) -> fetch -> parse.

    - Rewrites www.facebook.com to m.facebook.com for better unauthenticated access.
    - Returns a stable schema with meta diagnostics.
    """
    t0 = time.time()
    fetched_with = "requests"
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
            

    force_play = os.getenv("FBIG_FORCE_PLAYWRIGHT") == "1"
    storage_state = os.getenv("FBIG_STORAGE_STATE")

    html = None
    if not force_play:
        html = fetch_html(rewritten_url)

    if not html:
        from .play_fetcher import fetch_with_playwright
        html = fetch_with_playwright(rewritten_url, storage_state=storage_state)
        if html:
            fetched_with = "playwright_login" if storage_state else "playwright"

    if not html:
        return {
            "status": "error",
            "type": type_tag,
            "data": None,
            "meta": {
                "duration_ms": int((time.time() - t0) * 1000),
                "fetched_with": fetched_with,
                "was_rewritten": was_rewritten,
                "rewritten_url": rewritten_url if was_rewritten else None,
            },
            "error": "fetch_failed",
        }

    data = {
        "og:title": None,
        "og:description": None,
        "og:image": None,
        "og:url": None,
        "og:site_name": None,
    }

    try:
        if type_tag == "fb_page":
            data["basic"] = parse_fb_page_basic(html)
        elif type_tag == "fb_post":
            data["basic"] = parse_fb_post_basic(html)
        elif type_tag == "fb_group":
            data["basic"] = parse_fb_group_basic(html)
        elif type_tag == "fb_group_post":
            data["basic"] = parse_fb_group_post_basic(html)
        elif type_tag == "ig_profile":
            data["basic"] = parse_ig_profile_basic(html)
        elif type_tag == "ig_post":
            data["basic"] = parse_ig_post_basic(html)
        else:
            data["basic"] = {}
    except Exception as e:
        data["basic"] = {"error": str(e)}

    zh_basic = _format_basic_zh(type_tag, data.get("basic", {}))
    data["基礎資訊"] = zh_basic

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
        "基礎資訊": zh_basic,
        "meta": {
            "duration_ms": int((time.time() - t0) * 1000),
            "fetched_with": fetched_with,
            "was_rewritten": was_rewritten,
            "rewritten_url": rewritten_url if was_rewritten else None,
        },
        "error": None,
    }