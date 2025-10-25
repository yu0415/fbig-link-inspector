from .classifier import classify
from .fetcher import fetch_html
from .parser import (
    parse_fb_page_basic, parse_fb_post_basic,
    parse_fb_group_basic, parse_fb_group_post_basic,
    parse_ig_profile_basic, parse_ig_post_basic
)
import os
import time

from typing import Dict, Any, Optional



def _to_int_with_units(s: str) -> Optional[int]:
    """
    將含有單位的數字字串轉為整數：
    - 支援：1,234 / 1.2K / 3.4M / 5.6B
    - 支援：1.2萬 / 3.4億
    - 僅取第一個出現的數字與單位
    """
    import re
    if not s:
        return None
    m = re.search(r'([0-9]+(?:[.,][0-9]+)?)\s*(K|M|B|萬|億)?', s, flags=re.I)
    if not m:
        return None
    num = m.group(1).replace(",", "")
    try:
        val = float(num.replace(",", "."))
    except Exception:
        try:
            val = float(num)
        except Exception:
            return None
    unit = (m.group(2) or "").lower()
    mul = 1
    if unit == "k":
        mul = 1_000
    elif unit == "m":
        mul = 1_000_000
    elif unit == "b":
        mul = 1_000_000_000
    elif unit == "萬":
        mul = 10_000
    elif unit == "億":
        mul = 100_000_000
    return int(round(val * mul))


def _extract_followers_from_html(html: str) -> Optional[int]:
    """
    嘗試從 HTML 直接抽取追蹤數：
    - 優先找 JSON 欄位：followers_count / subscriber_count / page_fans_count / fan_count
    - 其次找文字展示：123,456 位追蹤者 / 12.3萬 粉絲 / 12.3K followers / 12,345 人追蹤
    """
    import re
    if not html:
        return None
    for pat in [
        r'"followers_count"\s*:\s*(\d+)',
        r'"subscriber_count"\s*:\s*(\d+)',
        r'"subscribers_count"\s*:\s*(\d+)',
        r'"page_fans_count"\s*:\s*(\d+)',
        r'"fan_count"\s*:\s*(\d+)',
        r'"follower_count"\s*:\s*(\d+)',
        r'"subscription_count"\s*:\s*(\d+)',
        r'"subscriberCount"\s*:\s*(\d+)',
    ]:
        m = re.search(pat, html, flags=re.I)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    for pat in [
        
        r'([0-9][0-9,\.]{0,12}\s*(?:K|M|B|萬|億)?)\s*(?:位)?\s*(?:追蹤者|粉絲|關注者|訂閱者)',
        r'([0-9][0-9,\.]{0,12}\s*(?:K|M|B|萬|億)?)\s*(?:人)?\s*(?:追蹤|關注|訂閱)',
        
        r'([0-9][0-9,\.]{0,12}\s*(?:K|M|B|萬|億)?)\s*followers',
        r'([0-9][0-9,\.]{0,12}\s*(?:K|M|B|萬|億)?)\s*subscribers',
    ]:
        m = re.search(pat, html, flags=re.I)
        if m:
            n = _to_int_with_units(m.group(1))
            if isinstance(n, int):
                return n
    return None

def _resolve_final_url_requests(url: str, timeout: int = 8) -> Optional[str]:
    """
    使用 requests 嘗試跟隨 share/r 等短連結的最終轉址（僅拿最終 URL，不取 HTML）
    """
    try:
        import requests
        r = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            },
        )
        if r.history and r.url:
            return r.url
    except Exception:
        pass
    return None

def _resolve_final_url_playwright(url: str, timeout_ms: int = 15000, storage_state: Optional[str] = None) -> Optional[str]:
    """
    使用 Playwright 瀏覽到 share/r 類型網址，等待 networkidle，回傳最終實際 URL。
    """
    try:
        from .play_fetcher import resolve_final_url as _resolve_url_play
        final_u = _resolve_url_play(url, timeout=int(timeout_ms/1000), storage_state=storage_state)
        return final_u
    except Exception:
        return None


def _extract_final_permalink_from_html(html: str) -> Optional[str]:
    """
    從 share/r 產生的 HTML 內文直接抽出最終 permalink（不依賴 HTTP 轉址）。
    兼容 www 與 m 版本，支援 GraphQL/Relay 欄位、canonical、以及頁內可見連結。
    回傳絕對網址（優先轉為 https://m.facebook.com/...）
    """
    import re
    try:
        
        def _to_m(u: str) -> str:
            if not u:
                return u
            u = u.replace("\\/", "/")
            u = u.replace("https://www.facebook.com", "https://m.facebook.com")
            u = u.replace("http://www.facebook.com", "https://m.facebook.com")
            u = u.replace("https://facebook.com", "https://m.facebook.com")
            u = u.replace("http://facebook.com", "https://m.facebook.com")
            if u.startswith("//www.facebook.com"):
                u = "https:" + u
                u = u.replace("https://www.facebook.com", "https://m.facebook.com")
            if u.startswith("//m.facebook.com"):
                u = "https:" + u
            if u.startswith("/"):
                u = "https://m.facebook.com" + u
            return u

        
        for pat in [
            r'"permalink_url"\s*:\s*"https:\\/\\/(?:www|m)\\.facebook\\.com\\/[^"\\]+?"',
            r'"permalinkURL"\s*:\s*"https:\\/\\/(?:www|m)\\.facebook\\.com\\/[^"\\]+?"',
            r'"canonical"\s*:\s*"https:\\/\\/(?:www|m)\\.facebook\\.com\\/[^"\\]+?"',
        ]:
            m = re.search(pat, html)
            if m:
                url = m.group(0).split(":", 1)[1].strip().strip('"')
                url = bytes(url, "utf-8").decode("unicode_escape")
                return _to_m(url)

        
        for pat in [
            r'https:\\/\\/www\\.facebook\\.com\\/[^"\\]+\\/posts\\/[0-9]+',
            r'https:\\/\\/m\\.facebook\\.com\\/[^"\\]+\\/posts\\/[0-9]+',
            r'https:\\/\\/www\\.facebook\\.com\\/[^"\\]+\\/videos\\/[0-9]+',
            r'https:\\/\\/m\\.facebook\\.com\\/[^"\\]+\\/videos\\/[0-9]+',
            r'https:\\/\\/www\\.facebook\\.com\\/reel\\/[0-9A-Za-z]+',
            r'https:\\/\\/m\\.facebook\\.com\\/reel\\/[0-9A-Za-z]+',
            r'https:\\/\\/www\\.facebook\\.com\\/photo\\.php\\?[^"\\]+',
            r'https:\\/\\/m\\.facebook\\.com\\/photo\\.php\\?[^"\\]+',
            r'https:\\/\\/www\\.facebook\\.com\\/story\\.php\\?[^"\\]+',
            r'https:\\/\\/m\\.facebook\\.com\\/story\\.php\\?[^"\\]+',
            r'https:\\/\\/www\\.facebook\\.com\\/permalink\\.php\\?[^"\\]+',
            r'https:\\/\\/m\\.facebook\\.com\\/permalink\\.php\\?[^"\\]+',
            r'https:\\/\\/www\\.facebook\\.com\\/watch\\/?\\?[^"\\]+',
            r'https:\\/\\/m\\.facebook\\.com\\/watch\\/?\\?[^"\\]+',
        ]:
            m = re.search(pat, html)
            if m:
                url = bytes(m.group(0), "utf-8").decode("unicode_escape")
                return _to_m(url)

        
        m = re.search(
            r'<iframe[^>]+src=["\'](https?://(?:www|m)\\.facebook\\.com/plugins/(?:post|video)\\.php\?[^"\']+)["\']',
            html, flags=re.I | re.S
        )
        if m:
            try:
                from urllib.parse import urlparse, parse_qs, unquote
                src_url = bytes(m.group(1), "utf-8").decode("unicode_escape").replace("&amp;", "&")
                q = urlparse(src_url).query
                hrefs = parse_qs(q).get("href")
                if hrefs and hrefs[0]:
                    return _to_m(unquote(hrefs[0]))
            except Exception:
                pass

        
        m = re.search(
            r'<link[^>]+rel=["\\\']canonical["\\\'][^>]+href=["\\\'](https://(?:www|m)\.facebook\.com/[^"\\\']+)["\\\']',
            html
        )
        if m:
            return _to_m(m.group(1))

        
        for pat in [
            r'href=["\\\'](/story\.php\?[^"\\\']+)["\\\']',
            r'href=["\\\'](/permalink\.php\?[^"\\\']+)["\\\']',
            r'href=["\\\'](https://m\.facebook\.com/[^"\\\']+/posts/\d+)["\\\']',
            r'href=["\\\'](https://m\.facebook\.com/[^"\\\']+/videos/\d+)["\\\']',
            r'href=["\\\'](https://m\.facebook\.com/reel/[^"\\\']+)["\\\']',
            r'href=["\\\'](/photo\.php\?[^"\\\']+)["\\\']',
            r'href=["\\\'](/watch/\\?[^"\\\']+)["\\\']',
        ]:
            m = re.search(pat, html)
            if m:
                return _to_m(m.group(1))

    except Exception:
        pass
    return None


def _extract_owner_id_from_html(html: str) -> Optional[str]:
    """
    從 HTML 中抽出 owner/page/profile 的數字 ID，常見鍵：owner_id/pageID/entity_id/profile_id。
    取得後可組成 https://m.facebook.com/profile.php?id=<ID>
    """
    import re
    try:
        for pat in [
            r'"owner_id"\s*:\s*"(\d+)"',
            r'"pageID"\s*:\s*"(\d+)"',
            r'"entity_id"\s*:\s*"(\d+)"',
            r'"profile_id"\s*:\s*"(\d+)"',
            r'data-owner-id=["\\\'](\d+)["\\\']',
            r'data-gt=["\\\'][^"\\\']*"profile_owner":"(\d+)"',
            
            r'"pageID"\s*:\s*(\d+)',
            r'"ownerID"\s*:\s*(\d+)',
            r'"page_id"\s*:\s*"(\d+)"',
            r'"page_id"\s*:\s*(\d+)',
            r'"actorID"\s*:\s*"(\d+)"',
        ]:
            m = re.search(pat, html)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def _extract_owner_slug_from_role_link(html: str) -> Optional[str]:
    """
    從新版 Reels/貼文頁中，專門抓取 <a role="link" ...> 內指向粉專頁名的 anchor，
    僅回傳 slug，不含路徑與查詢字串。會排除常見非 owner 的路徑。
    """
    import re
    if not html:
        return None

    bad_first = {
        "share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
        "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"
    }
    allowed_next = {"", "reels", "posts", "videos", "photos", "about", "pg", "timeline"}

    def good_pair(first: str, nxt: Optional[str]) -> bool:
        first = (first or "").strip().lower()
        nxt = (nxt or "").strip().lower()
        if not first or first in bad_first:
            return False
        return nxt in allowed_next

    
    m = re.search(
        r'<a[^>]+role=["\']link["\'][^>]+href=["\']https?://(?:www|m)\\.facebook\\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\\?[^"\']*)?["\']',
        html,
        flags=re.I | re.S,
    )
    if m and good_pair(m.group(1), m.group(2)):
        return m.group(1)

    
    m = re.search(
        r'<a[^>]+role=["\']link["\'][^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\\?[^"\']*)?["\']',
        html,
        flags=re.I | re.S,
    )
    if m and good_pair(m.group(1), m.group(2)):
        return m.group(1)

    return None

def _extract_owner_slug_from_html(html: str) -> Optional[str]:
    """
    從 HTML/JSON 片段裡推測粉專 slug（優先找 slug 而非 profile.php），
    支援：
      - JSON 轉義的 https:\/\/(www|m).facebook.com/<slug>?...
      - <a ... href="https://(www|m).facebook.com/<slug>[/(reels|posts|videos|photos|about|pg|timeline)]?...">
      - <a ... href="/<slug>[/(reels|posts|videos|photos|about|pg|timeline)]?...">
    排除常見非 owner 的路徑：
      share / reel / watch / photo.php / story.php / permalink.php / marketplace / gaming / friends / groups /
      profile.php / data / privacy_sandbox / help / settings / policy / login / pages
    """
    import re
    if not html:
        return None

    bad_first = {
        "share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
        "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"
    }
    allowed_next = {"", "reels", "posts", "videos", "photos", "about", "pg", "timeline"}

    def good_pair(first: str, nxt: Optional[str]) -> bool:
        first = (first or "").strip().lower()
        nxt = (nxt or "").strip().lower()
        if not first or first in bad_first:
            return False
        return nxt in allowed_next

    
    m = re.search(
        r'https:\\/\\/(?:www|m)\\.facebook\\.com\\/([A-Za-z0-9._-]+)(?:\\/([A-Za-z0-9._-]+))?(?:\\?[^"\\\\]*)?',
        html
    )
    if m and good_pair(m.group(1), m.group(2)):
        return m.group(1)

    
    m = re.search(
        r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
        html, flags=re.I | re.S
    )
    if m and good_pair(m.group(1), m.group(2)):
        return m.group(1)

    
    m = re.search(r'href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']', html)
    if m and good_pair(m.group(1), m.group(2)):
        return m.group(1)

    return None



def _extract_owner_from_anchors(html: str) -> Optional[str]:
    """
    從 HTML 的 <a href=...> 直接抽出粉專 slug（優先 www/m 絕對連結，再試相對連結）。
    僅回傳 slug，不含路徑與查詢字串。會排除常見非 owner 的路徑。
    """
    import re
    if not html:
        return None

    bad_first = {
        "share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
        "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"
    }
    allowed_next = {"", "reels", "posts", "videos", "photos", "about", "pg", "timeline"}

    def good_pair(first: str, nxt: Optional[str]) -> bool:
        first = (first or "").strip().lower()
        nxt = (nxt or "").strip().lower()
        if not first or first in bad_first:
            return False
        return nxt in allowed_next

    
    for m in re.finditer(
        r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
        html, flags=re.I | re.S
    ):
        if good_pair(m.group(1), m.group(2)):
            return m.group(1)

    
    for m in re.finditer(
        r'<a[^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
        html, flags=re.I | re.S
    ):
        if good_pair(m.group(1), m.group(2)):
            return m.group(1)

    return None


def _extract_owner_display_name(html: str) -> Optional[str]:
    """
    從 m.facebook DOM 抽取擁有者顯示名稱（例如 h2/anchor 內的文字：ETtoday新聞雲）。
    僅回傳純文字名稱，不含表情或額外空白。
    """
    if not html:
        return None
    try:
        import re
        
        m = re.search(
            r'<a[^>]+aria-label=["\'].*?(查看擁有者個人檔案|查看粉絲專頁|View owner profile|View Page).*?["\'][^>]*>(.*?)</a>',
            html, flags=re.I | re.S
        )
        def _strip(t: str) -> str:
            t = re.sub(r'<[^>]+>', '', t or '')
            t = re.sub(r'\s+', ' ', t).strip()
            return t

        if m:
            name = _strip(m.group(2))
            if name:
                return name

        
        m = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>.*?</h2>', html, flags=re.I | re.S)
        if m:
            name = _strip(m.group(1))
            if name:
                return name

        
        m = re.search(r'<a[^>]+role=["\']link["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S)
        if m:
            name = _strip(m.group(1))
            if name:
                return name
        return None
    except Exception:
        return None


def _extract_page_slug_by_label(html: str) -> Optional[str]:
    """
    從帶有「粉絲專頁 / Page」語意的 aria-label 或可見文字的 <a> 取得粉專 slug。
    僅回傳 slug，若未命中回傳 None。
    """
    if not html:
        return None
    try:
        import re
        bad_first = {
            "share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
            "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"
        }
        allowed_next = {"", "reels", "posts", "videos", "photos", "about", "pg", "timeline"}

        def good_pair(first: str, nxt: str) -> bool:
            first = (first or "").strip().lower()
            nxt = (nxt or "").strip().lower()
            if not first or first in bad_first:
                return False
            return nxt in allowed_next

        
        m = re.search(
            r'<a[^>]+aria-label=["\'][^"\']*(?:粉絲專頁|Page)[^"\']*["\'][^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
            html, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return m.group(1)

        
        m = re.search(
            r'<a[^>]+aria-label=["\'][^"\']*(?:粉絲專頁|Page)[^"\']*["\'][^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
            html, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return m.group(1)

        
        m = re.search(
            r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\'][^>]*>[^<]*(?:粉絲專頁|Page)[^<]*</a>',
            html, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return m.group(1)

        
        m = re.search(
            r'<a[^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\'][^>]*>[^<]*(?:粉絲專頁|Page)[^<]*</a>',
            html, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return m.group(1)

    except Exception:
        return None
    return None


def _upgrade_profile_to_page_slug(owner_url: Optional[str], storage_state: Optional[str] = None) -> Optional[str]:
    """
    若 owner_url 是 profile.php?id=...，嘗試開啟該頁並從頁內抽取可用的粉專 slug，
    成功則回傳 https://m.facebook.com/<slug>，失敗回傳 None。
    掃描策略：
      1) 先用現有 `_extract_owner_slug_from_html`（支援 JSON 轉義 / 絕對 / 相對錨點）。
      2) 備援：掃描頁內 `<a href="https://(www|m).facebook.com/<slug>...">` 與相對 `/ <slug>`，排除常見非 owner 路徑。
    """
    if not owner_url or "profile.php" not in owner_url:
        return None
    try:
        
        html_owner = None
        if storage_state:
            from .play_fetcher import fetch_with_playwright as _play_fetch
            html_owner = _play_fetch(owner_url, storage_state=storage_state)
        if not html_owner:
            from .fetcher import fetch_html as _fetch_html
            html_owner = _fetch_html(owner_url)
        if not html_owner:
            return None

        
        slug = _extract_owner_slug_from_html(html_owner)
        if slug:
            return f"https://m.facebook.com/{slug}"

        
        import re
        bad_first = {
            "share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
            "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"
        }
        allowed_next = {"", "reels", "posts", "videos", "photos", "about", "pg", "timeline"}

        def good_pair(first: str, nxt: str) -> bool:
            first = (first or "").strip().lower()
            nxt = (nxt or "").strip().lower()
            if not first or first in bad_first:
                return False
            return nxt in allowed_next

        m = re.search(
            r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
            html_owner, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return f"https://m.facebook.com/{m.group(1)}"

        m = re.search(
            r'<a[^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
            html_owner, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return f"https://m.facebook.com/{m.group(1)}"
    except Exception:
        return None
    return None

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

    
    try:
        
        if type_tag in ("fb_post", "fb_group_post"):
            basic = data.get("basic") or {}
            
            if not basic.get("owner_url"):
                import re as _reG
                slugG = None
                m = _reG.search(r'href="/([A-Za-z0-9._-]+)/reels/', html)
                if m:
                    slugG = m.group(1)
                if not slugG:
                    m = _reG.search(r'href="/([A-Za-z0-9._-]+)\?[^\"]*ref=content_permalink', html)
                    if m:
                        slugG = m.group(1)
                if not slugG:
                    m = _reG.search(r'"ownerProfileUrl"\s*:\s*"https:\\/\\/m\\.facebook\\.com\\/([^"\\]+)"', html)
                    if m:
                        slugG = m.group(1).split("\\/")[0]
                
                if not slugG:
                    m = _reG.search(
                        r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
                        html,
                        flags=_reG.I | _reG.S
                    )
                    if m:
                        cand, nxt = m.group(1), (m.group(2) or "").lower()
                        bad = {"share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
                               "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"}
                        allowed_next = {"","reels","posts","videos","photos","about","pg","timeline"}
                        if cand.lower() not in bad and nxt in allowed_next:
                            slugG = cand
                if slugG and slugG.lower() not in ("share", "reel", "watch", "photo.php", "story.php", "permalink.php", "marketplace", "gaming", "friends"):
                    data.setdefault("basic", {})["owner_url"] = f"https://m.facebook.com/{slugG}"
                if not data["basic"].get("owner_url"):
                    m = _reG.search(r'href="/profile\.php\?[^\"]*\bid=(\d+)', html)
                    if m:
                        data["basic"]["owner_url"] = f"https://m.facebook.com/profile.php?id={m.group(1)}"
                if not data["basic"].get("owner_url"):
                    m = _reG.search(r'href="/([A-Za-z0-9._-]+)/\?[^\"]*reels_tab', html)
                    if m:
                        _slug2 = m.group(1)
                        if _slug2.lower() not in ("share", "reel", "watch", "photo.php", "story.php", "permalink.php", "marketplace", "gaming", "friends"):
                            data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug2}"
                
                if not data["basic"].get("owner_url") and not slugG:
                    _slug_auto = _extract_owner_slug_from_html(html)
                    if _slug_auto:
                        data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_auto}"
            
            if not data["basic"].get("owner_url"):
                m = _reG.search(r'aria-label="查看擁有者個人檔案"[^>]+href="(/profile\.php\?[^"\\\']+)"', html)
                if not m:
                    
                    m = _reG.search(r'aria-label="View owner profile"[^>]+href="(/profile\.php\?[^"\\\']+)"', html)
                if m:
                    href = m.group(1).replace("&amp;", "&")
                    from urllib.parse import urljoin
                    owner_url = urljoin("https://m.facebook.com", href.split("&")[0])
                    data["basic"]["owner_url"] = owner_url
            
            if not data["basic"].get("owner_url"):
                _slug_role = _extract_owner_slug_from_role_link(html)
                if _slug_role:
                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_role}"
            
            if not data["basic"].get("owner_url") or "profile.php" in (data["basic"].get("owner_url") or ""):
                _slug_from_a = _extract_owner_from_anchors(html)
                if _slug_from_a:
                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_from_a}"

            
            try:
                cur_owner = data["basic"].get("owner_url")
                if cur_owner and "profile.php" in cur_owner and "/groups/" not in cur_owner:
                    upgraded = _upgrade_profile_to_page_slug(cur_owner, storage_state)
                    if upgraded:
                        data["basic"]["owner_url"] = upgraded
            except Exception:
                pass
            
            
            if data["basic"].get("owner_url"):
                _owner_now = data["basic"]["owner_url"]
                
                _bad_roots = ("/friends", "/marketplace", "/gaming")
                _looks_bad = any(br in _owner_now for br in _bad_roots)
                
                m2 = _reG.search(r'aria-label="查看擁有者個人檔案"[^>]+href="(/profile\.php\?[^"\\\']+)"', html) or \
                     _reG.search(r'aria-label="View owner profile"[^>]+href="(/profile\.php\?[^"\\\']+)"', html)
                if (_looks_bad or _owner_now.endswith("id=0") or _owner_now.endswith("id=1")) and m2:
                    href2 = m2.group(1).replace("&amp;", "&")
                    from urllib.parse import urljoin
                    data["basic"]["owner_url"] = urljoin("https://m.facebook.com", href2.split("&")[0])

            
            if not data.get("basic", {}).get("owner_name"):
                dn = _extract_owner_display_name(html or "")
                if dn:
                    data.setdefault("basic", {})["owner_name"] = dn

            
            
            try:
                import re as _reABS
                cur_owner = data["basic"].get("owner_url")
                need_fix = bool(cur_owner and "profile.php" in cur_owner and "/groups/" not in cur_owner)
                
                if not need_fix:
                    need_fix = (data["basic"].get("page_followers") is None)
                if need_fix:
                    m_abs = _reABS.search(
                         r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:\?[^"\']*)?["\']',
                         html,
                         flags=_reABS.I | _reABS.S
                    )
                    if m_abs:
                        _slug = m_abs.group(1)
                        if _slug.lower() not in ("share", "reel", "watch", "photo.php", "story.php", "permalink.php", "marketplace", "gaming", "friends"):
                            data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug}"
            except Exception:
                pass

            owner_for_follow = data.get("basic", {}).get("owner_url")
            
            if not data.get("basic", {}).get("owner_name"):
                
                try:
                    html_owner2 = fetch_html(owner_for_follow)
                except Exception:
                    html_owner2 = None
                dn2 = _extract_owner_display_name(html_owner2 or "")
                if dn2:
                    data.setdefault("basic", {})["owner_name"] = dn2
            if owner_for_follow and (data["basic"].get("page_followers") is None and "/groups/" not in owner_for_follow):
                
                html_owner = None
                if storage_state:
                    from .play_fetcher import fetch_with_playwright as _play_fetch
                    html_owner = _play_fetch(owner_for_follow, storage_state=storage_state)
                if not html_owner:
                    html_owner = fetch_html(owner_for_follow)
                
                try:
                    if "profile.php" in owner_for_follow and "/groups/" not in owner_for_follow and html_owner:
                        import re as _refix
                        mslug = _refix.search(
                            r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:\?[^"\']*)?["\']',
                            html_owner,
                            flags=_refix.I | _refix.S
                        )
                        if mslug:
                            cand = mslug.group(1)
                            bad = {"share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
                                   "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"}
                            if cand.lower() not in bad:
                                
                                owner_for_follow = f"https://m.facebook.com/{cand}"
                                data.setdefault("basic", {})["owner_url"] = owner_for_follow
                                html_owner = None
                                if storage_state:
                                    from .play_fetcher import fetch_with_playwright as _play_fetch
                                    html_owner = _play_fetch(owner_for_follow, storage_state=storage_state)
                                if not html_owner:
                                    html_owner = fetch_html(owner_for_follow)
                except Exception:
                    pass
                if html_owner:
                    page_basic = parse_fb_page_basic(html_owner)
                    if page_basic.get("followers") is not None:
                        data["basic"]["page_followers"] = page_basic["followers"]
                    if data["basic"].get("page_followers") is None:
                        n = _extract_followers_from_html(html_owner)
                        if isinstance(n, int):
                            data["basic"]["page_followers"] = n
                    if data["basic"].get("page_followers") is None:
                        
                        n_vis = _extract_followers_from_html(html_owner)
                        if isinstance(n_vis, int):
                            data["basic"]["page_followers"] = n_vis
                    if data["basic"].get("page_followers") is None:
                        variants = []
                        base = owner_for_follow.rstrip("/")
                        if "profile.php?id=" in owner_for_follow:
                            sep = "&" if "?" in owner_for_follow else "?"
                            variants += [
                                f"{owner_for_follow}{sep}sk=followers",
                                f"{owner_for_follow}{sep}v=followers",
                            ]
                        else:
                            variants += [f"{base}/about", f"{base}?v=followers"]
                        for ov in variants:
                            html_owner2 = None
                            if storage_state:
                                from .play_fetcher import fetch_with_playwright as _play_fetch
                                html_owner2 = _play_fetch(ov, storage_state=storage_state)
                            if not html_owner2:
                                html_owner2 = fetch_html(ov)
                            if not html_owner2:
                                continue
                            pb2 = parse_fb_page_basic(html_owner2)
                            if pb2.get("followers") is not None:
                                data["basic"]["page_followers"] = pb2["followers"]
                                break
                            n2 = _extract_followers_from_html(html_owner2)
                            if isinstance(n2, int):
                                data["basic"]["page_followers"] = n2
                                break
            elif owner_for_follow and "/groups/" in owner_for_follow and data["basic"].get("group_members") is None:
                
                html_owner = None
                if storage_state:
                    from .play_fetcher import fetch_with_playwright as _play_fetch
                    html_owner = _play_fetch(owner_for_follow, storage_state=storage_state)
                if not html_owner:
                    html_owner = fetch_html(owner_for_follow)
                if html_owner:
                    grp_basic = parse_fb_group_basic(html_owner)
                    if grp_basic.get("members") is not None:
                        data["basic"]["group_members"] = grp_basic["members"]

        
        if type_tag == "ig_post":
            basic = data.get("basic") or {}
            if basic.get("owner_followers") is None:
                import re as _reI
                uname = None
                m = _reI.search(r'"ownerUsername"\s*:\s*"([^"]+)"', html)
                if m:
                    uname = m.group(1)
                if not uname:
                    m = _reI.search(r'href="/([A-Za-z0-9._]+)/\?__a=', html)
                    if m:
                        uname = m.group(1)
                if not uname:
                    m = _reI.search(r'href="/([A-Za-z0-9._]+)/"', html)
                    if m:
                        uname = m.group(1)
                if uname:
                    prof = f"https://www.instagram.com/{uname}/"
                    html_prof = None
                    if storage_state:
                        from .play_fetcher import fetch_with_playwright as _play_fetch
                        html_prof = _play_fetch(prof, storage_state=storage_state)
                    if not html_prof:
                        html_prof = fetch_html(prof)
                    if html_prof:
                        pro_basic = parse_ig_profile_basic(html_prof)
                        if pro_basic.get("followers") is not None:
                            data.setdefault("basic", {})["owner_followers"] = pro_basic["followers"]
    except Exception:
        pass

    
    try:
        is_fb_share = "facebook.com/share/" in (rewritten_url or url)
        if type_tag in ("fb_post", "fb_group_post") and is_fb_share:
            basic = data.get("basic") or {}
            owner_url = basic.get("owner_url")
            if (not owner_url) or (basic.get("page_followers") is None):
                storage_state = os.getenv("FBIG_STORAGE_STATE") or None
                
                final_u = (
                    _resolve_final_url_playwright(rewritten_url or url, storage_state=storage_state)
                    or _resolve_final_url_requests(rewritten_url or url)
                )
                
                if (not final_u) or ("facebook.com/share/" in final_u):
                    
                    html_source = html if isinstance(html, str) else ""
                    extracted = _extract_final_permalink_from_html(html_source)
                    if extracted:
                        final_u = extracted

                
                if (not final_u) and (not owner_url):
                    owner_id = _extract_owner_id_from_html(html_source)
                    if owner_id:
                        derived_owner = f"https://m.facebook.com/profile.php?id={owner_id}"
                        data.setdefault("basic", {})["owner_url"] = derived_owner
                        
                        html_owner = None
                        if storage_state:
                            from .play_fetcher import fetch_with_playwright as _play_fetch
                            html_owner = _play_fetch(derived_owner, storage_state=storage_state)
                        if not html_owner:
                            html_owner = fetch_html(derived_owner)
                        if html_owner:
                            page_basic = parse_fb_page_basic(html_owner)
                            if page_basic.get("followers") is not None:
                                data["basic"]["page_followers"] = page_basic["followers"]

                if final_u and "facebook.com/share/" not in final_u:
                    
                    final_u = final_u.replace("https://www.facebook.com", "https://m.facebook.com")

                    
                    import re as _re
                    derived_owner = None
                    try:
                        
                        m = _re.search(r"https://m\.facebook\.com/([A-Za-z0-9._-]+)/posts/\d+", final_u)
                        if m:
                            derived_owner = f"https://m.facebook.com/{m.group(1)}"
                        
                        if not derived_owner:
                            m = _re.search(r"https://m\.facebook\.com/([A-Za-z0-9._-]+)/videos/\d+", final_u)
                            if m:
                                derived_owner = f"https://m.facebook.com/{m.group(1)}"
                        
                        if not derived_owner:
                            m = _re.search(r"https://m\.facebook\.com/story\.php\?[^#]*\bid=(\d+)", final_u)
                            if m:
                                derived_owner = f"https://m.facebook.com/profile.php?id={m.group(1)}"
                        
                        if not derived_owner:
                            m = _re.search(r"https://m\.facebook\.com/permalink\.php\?[^#]*\bid=(\d+)", final_u)
                            if m:
                                derived_owner = f"https://m.facebook.com/profile.php?id={m.group(1)}"
                        
                        if not derived_owner:
                            m = _re.search(r"https://m\.facebook\.com/groups/([A-Za-z0-9._-]+)/posts/\d+", final_u)
                            if m:
                                derived_owner = f"https://m.facebook.com/groups/{m.group(1)}"
                    except Exception:
                        pass

                    
                    if derived_owner:
                        data.setdefault("basic", {})["owner_url"] = derived_owner
                        
                        if not data.get("basic", {}).get("owner_name"):
                            dn = _extract_owner_display_name(html or "")
                            if dn:
                                data.setdefault("basic", {})["owner_name"] = dn
                        
                        try:
                            curr = data.get("basic", {}).get("owner_url")
                            upgraded = _upgrade_profile_to_page_slug(curr, storage_state)
                            if upgraded:
                                data["basic"]["owner_url"] = upgraded
                        except Exception:
                            pass
                        
                        html_owner = None
                        if storage_state:
                            from .play_fetcher import fetch_with_playwright as _play_fetch
                            html_owner = _play_fetch(derived_owner, storage_state=storage_state)
                        if not html_owner:
                            html_owner = fetch_html(derived_owner)
                        if html_owner:
                            if "/groups/" in derived_owner:
                                grp_basic = parse_fb_group_basic(html_owner)
                                if grp_basic.get("members") is not None:
                                    data["basic"]["group_members"] = grp_basic["members"]
                                    if "基礎資訊" in data and "基礎資訊" in locals():
                                        pass
                            else:
                                        page_basic = parse_fb_page_basic(html_owner)
                                        if page_basic.get("followers") is not None:
                                            data["basic"]["page_followers"] = page_basic["followers"]

                                        
                                        if data["basic"].get("page_followers") is None:
                                            n = _extract_followers_from_html(html_owner)
                                            if isinstance(n, int):
                                                data["basic"]["page_followers"] = n

                                        
                                        if data["basic"].get("page_followers") is None:
                                            variants = []
                                            base = derived_owner.rstrip("/")
                                            if "profile.php?id=" in derived_owner:
                                                sep = "&" if "?" in derived_owner else "?"
                                                variants += [
                                                    f"{derived_owner}{sep}sk=followers",
                                                    f"{derived_owner}{sep}v=followers",
                                                ]
                                            else:
                                                variants += [f"{base}/about", f"{base}?v=followers"]

                                            for ov in variants:
                                                html_owner2 = None
                                                if storage_state:
                                                    from .play_fetcher import fetch_with_playwright as _play_fetch
                                                    html_owner2 = _play_fetch(ov, storage_state=storage_state)
                                                if not html_owner2:
                                                    html_owner2 = fetch_html(ov)
                                                if not html_owner2:
                                                    continue

                                                pb2 = parse_fb_page_basic(html_owner2)
                                                if pb2.get("followers") is not None:
                                                    data["basic"]["page_followers"] = pb2["followers"]
                                                    break

                                                n2 = _extract_followers_from_html(html_owner2)
                                                if isinstance(n2, int):
                                                    data["basic"]["page_followers"] = n2
                                                    break

                    data["final_permalink"] = final_u

                    
                    html2 = None
                    if storage_state:
                        from .play_fetcher import fetch_with_playwright as _play_fetch
                        html2 = _play_fetch(final_u, storage_state=storage_state)
                    if not html2:
                        html2 = fetch_html(final_u)
                    if html2:
                        
                        try:
                            basic2 = parse_fb_post_basic(html2)
                            if basic2.get("owner_url"):
                                data["basic"]["owner_url"] = basic2["owner_url"]

                            
                            if not data["basic"].get("owner_url"):
                                owner_id2 = _extract_owner_id_from_html(html2)
                                if owner_id2:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/profile.php?id={owner_id2}"

                            
                            if not data["basic"].get("owner_url"):
                                import re as _re2
                                slug = None
                                
                                m = _re2.search(r'href="/([A-Za-z0-9._-]+)/reels/', html2)
                                if m:
                                    slug = m.group(1)
                                
                                if not slug:
                                    m = _re2.search(r'href="/([A-Za-z0-9._-]+)\?[^"]*ref=content_permalink', html2)
                                    if m:
                                        slug = m.group(1)
                                
                                if not slug:
                                    m = _re2.search(r'"ownerProfileUrl"\s*:\s*"https:\\/\\/m\\.facebook\\.com\\/([^"\\]+)"', html2)
                                    if m:
                                        slug = m.group(1).split("\\/")[0]
                                
                                if not data["basic"].get("owner_url") and not slug:
                                    m = _re2.search(
                                        r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
                                        html2,
                                        flags=_re2.I | _re2.S
                                    )
                                    if m:
                                        cand, nxt = m.group(1), (m.group(2) or "").lower()
                                        bad = {"share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
                                               "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"}
                                        allowed_next = {"","reels","posts","videos","photos","about","pg","timeline"}
                                        if cand.lower() not in bad and nxt in allowed_next:
                                            slug = cand
                                
                                if not slug and not data["basic"].get("owner_url"):
                                    _slug_auto2 = _extract_owner_slug_from_html(html2)
                                    if _slug_auto2:
                                        slug = _slug_auto2
                                if slug and slug.lower() not in ("share", "reel", "watch", "photo.php", "story.php", "permalink.php", "marketplace", "gaming", "friends"):
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{slug}"
                            
                            if not data["basic"].get("owner_url"):
                                m = _re2.search(r'aria-label="查看擁有者個人檔案"[^>]+href="(/profile\.php\?[^"\\\']+)"', html2)
                                if not m:
                                    m = _re2.search(r'aria-label="View owner profile"[^>]+href="(/profile\.php\?[^"\\\']+)"', html2)
                                if m:
                                    href = m.group(1).replace("&amp;", "&")
                                    from urllib.parse import urljoin
                                    owner_url = urljoin("https://m.facebook.com", href.split("&")[0])
                                    data["basic"]["owner_url"] = owner_url

                            
                            
                            need_override = (data["basic"].get("page_followers") is None)
                            if need_override:
                                m_override = _re2.search(r'aria-label="查看擁有者個人檔案"[^>]+href="(/profile\.php\?[^"\\\']+)"', html2) or \
                                              _re2.search(r'aria-label="View owner profile"[^>]+href="(/profile\.php\?[^"\\\']+)"', html2)
                                if m_override:
                                    href_ov = m_override.group(1).replace("&amp;", "&")
                                    from urllib.parse import urljoin
                                    owner_candidate = urljoin("https://m.facebook.com", href_ov.split("&")[0])
                                    cur = data["basic"].get("owner_url")
                                    
                                    _bad_roots = ("/friends", "/marketplace", "/gaming")
                                    if (cur is None) or any(br in (cur or "") for br in _bad_roots):
                                        data["basic"]["owner_url"] = owner_candidate

                            
                            
                            try:
                                import re as _reABS2
                                cur_owner2 = data["basic"].get("owner_url")
                                need_fix2 = bool(cur_owner2 and "profile.php" in cur_owner2 and "/groups/" not in cur_owner2)
                                if not need_fix2:
                                    need_fix2 = (data["basic"].get("page_followers") is None)
                                if need_fix2:
                                    m_abs2 = _reABS2.search(r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:\?[^"\']*)?["\']',html2,flags=_reABS2.I | _reABS2.S)
                                    if m_abs2:
                                        _slug2 = m_abs2.group(1)
                                        if _slug2.lower() not in ("share", "reel", "watch", "photo.php", "story.php", "permalink.php", "marketplace", "gaming", "friends"):
                                            data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug2}"
                            except Exception:
                                pass

                            
                            
                            if not data["basic"].get("owner_url"):
                                import re as _reANY
                                bad_first = {"share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
                                            "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"}
                                allowed_next = {"","reels","posts","videos","photos","about","pg","timeline"}
                                
                                m = _reANY.search(
                                    r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
                                    html2, flags=_reANY.I | _reANY.S
                                )
                                if m:
                                    cand, nxt = m.group(1), (m.group(2) or "").lower()
                                    if cand.lower() not in bad_first and nxt in allowed_next:
                                        data["basic"]["owner_url"] = f"https://m.facebook.com/{cand}"
                                
                                if not data["basic"].get("owner_url"):
                                    m = _reANY.search(
                                        r'<a[^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
                                        html2, flags=_reANY.I | _reANY.S
                                    )
                                    if m:
                                        cand, nxt = m.group(1), (m.group(2) or "").lower()
                                        if cand.lower() not in bad_first and nxt in allowed_next:
                                            data["basic"]["owner_url"] = f"https://m.facebook.com/{cand}"

                            
                            owner_for_follow = data["basic"].get("owner_url")
                            if data["basic"].get("page_followers") is None and owner_for_follow:
                                html_owner = None
                                if storage_state:
                                    from .play_fetcher import fetch_with_playwright as _play_fetch
                                    html_owner = _play_fetch(owner_for_follow, storage_state=storage_state)
                                if not html_owner:
                                    html_owner = fetch_html(owner_for_follow)
                                if html_owner:
                                    if "/groups/" in owner_for_follow:
                                        grp_basic = parse_fb_group_basic(html_owner)
                                        if grp_basic.get("members") is not None:
                                            data["basic"]["group_members"] = grp_basic["members"]
                                    else:
                                        page_basic = parse_fb_page_basic(html_owner)
                                        if page_basic.get("followers") is not None:
                                            data["basic"]["page_followers"] = page_basic["followers"]
                            
                            cur_owner_tmp = data["basic"].get("owner_url")
                            if (not cur_owner_tmp) or ("profile.php" in cur_owner_tmp):
                                _slug_by_label = _extract_page_slug_by_label(html2)
                                if not _slug_by_label:
                                    _slug_by_label = _extract_page_slug_by_label(html)  
                                if _slug_by_label:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_by_label}"

                            
                            if not data["basic"].get("owner_url"):
                                _slug_role2 = _extract_owner_slug_from_role_link(html2) or _extract_owner_slug_from_role_link(html)
                                if _slug_role2:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_role2}"
                            
                            if not data["basic"].get("owner_url") or "profile.php" in (data["basic"].get("owner_url") or ""):
                                _slug_from_a2 = _extract_owner_from_anchors(html2)
                                if _slug_from_a2:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_from_a2}"

                            
                            
                            
                            
                            cur_owner = data["basic"].get("owner_url")
                            if cur_owner and "profile.php" in cur_owner:
                                _slug_final = _extract_owner_from_anchors(html2) or _extract_owner_from_anchors(html)
                                if _slug_final:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_final}"
                                    cur_owner = data["basic"]["owner_url"]

                            
                            if data["basic"].get("page_followers") is None and data["basic"].get("owner_url") and "/groups/" not in data["basic"]["owner_url"]:
                                owner_for_follow = data["basic"]["owner_url"]
                                html_owner = None
                                if storage_state:
                                    from .play_fetcher import fetch_with_playwright as _play_fetch
                                    html_owner = _play_fetch(owner_for_follow, storage_state=storage_state)
                                if not html_owner:
                                    html_owner = fetch_html(owner_for_follow)
                                if html_owner:
                                    page_basic = parse_fb_page_basic(html_owner)
                                    if page_basic.get("followers") is not None:
                                        data["basic"]["page_followers"] = page_basic["followers"]
                                    if data["basic"].get("page_followers") is None:
                                        n2 = _extract_followers_from_html(html_owner)
                                        if isinstance(n2, int):
                                            data["basic"]["page_followers"] = n2
                        except Exception:
                            pass
                    
                    rewritten_url = final_u or rewritten_url
                    was_rewritten = was_rewritten or bool(final_u and final_u != url)
    except Exception:
        pass

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
            "final_permalink": data.get("final_permalink"),
        },
        "error": None,
    }