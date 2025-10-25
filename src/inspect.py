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


# --- followers extract util ---
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
        # zh / zh-TW variants
        r'([0-9][0-9,\.]{0,12}\s*(?:K|M|B|萬|億)?)\s*(?:位)?\s*(?:追蹤者|粉絲|關注者|訂閱者)',
        r'([0-9][0-9,\.]{0,12}\s*(?:K|M|B|萬|億)?)\s*(?:人)?\s*(?:追蹤|關注|訂閱)',
        # en variants
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
        # 小工具：標準化輸出為 m.facebook.com
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

        # 1) GraphQL/Relay 常見鍵（www / m）
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

        # 2) JSON 片段中的常見 permalink 形態（www / m）
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

        # 2.5) <iframe src="https://www.facebook.com/plugins/post.php?href=..."> 或 video.php 內含最終 href
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

        # 3) <link rel="canonical" ...>（www / m）
        m = re.search(
            r'<link[^>]+rel=["\\\']canonical["\\\'][^>]+href=["\\\'](https://(?:www|m)\.facebook\.com/[^"\\\']+)["\\\']',
            html
        )
        if m:
            return _to_m(m.group(1))

        # 4) 頁內可見連結（未轉義形式）
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
            # --- additional patterns ---
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

# --- New helper: extract owner slug from HTML ---
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

    # 1) 絕對連結：<a role="link" href="https://(www|m).facebook.com/<slug>(/next)?...">
    m = re.search(
        r'<a[^>]+role=["\']link["\'][^>]+href=["\']https?://(?:www|m)\\.facebook\\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\\?[^"\']*)?["\']',
        html,
        flags=re.I | re.S,
    )
    if m and good_pair(m.group(1), m.group(2)):
        return m.group(1)

    # 2) 相對連結：<a role="link" href="/<slug>(/next)?...">
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

    # A) JSON-escaped absolute，捕捉第一段與下一段
    m = re.search(
        r'https:\\/\\/(?:www|m)\\.facebook\\.com\\/([A-Za-z0-9._-]+)(?:\\/([A-Za-z0-9._-]+))?(?:\\?[^"\\\\]*)?',
        html
    )
    if m and good_pair(m.group(1), m.group(2)):
        return m.group(1)

    # B) Normal absolute anchor（單/雙引號、跨行）
    m = re.search(
        r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
        html, flags=re.I | re.S
    )
    if m and good_pair(m.group(1), m.group(2)):
        return m.group(1)

    # C) Relative anchor
    m = re.search(r'href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']', html)
    if m and good_pair(m.group(1), m.group(2)):
        return m.group(1)

    return None


# 新增：直接從 anchor 絕對/相對連結抽 slug
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

    # 1) 絕對連結（優先）：掃描全部 <a href="https://(www|m).facebook.com/...">
    for m in re.finditer(
        r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
        html, flags=re.I | re.S
    ):
        if good_pair(m.group(1), m.group(2)):
            return m.group(1)

    # 2) 相對連結：掃描全部 <a href="/<slug>[/(...)]?">
    for m in re.finditer(
        r'<a[^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
        html, flags=re.I | re.S
    ):
        if good_pair(m.group(1), m.group(2)):
            return m.group(1)

    return None

# 新增：從 m.facebook DOM 抽取擁有者顯示名稱（例如 h2/anchor 內的文字：ETtoday新聞雲）
def _extract_owner_display_name(html: str) -> Optional[str]:
    """
    從 m.facebook DOM 抽取擁有者顯示名稱（例如 h2/anchor 內的文字：ETtoday新聞雲）。
    僅回傳純文字名稱，不含表情或額外空白。
    """
    if not html:
        return None
    try:
        import re
        # 優先：aria-label 包含「查看擁有者個人檔案」或「查看粉絲專頁」或英文對應的 anchor 之可見文字
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

        # 次要：h2 裡的第一個 anchor 文字（常見於粉專名稱區塊）
        m = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>.*?</h2>', html, flags=re.I | re.S)
        if m:
            name = _strip(m.group(1))
            if name:
                return name

        # 最後：role="link" 的 anchor 文字
        m = re.search(r'<a[^>]+role=["\']link["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S)
        if m:
            name = _strip(m.group(1))
            if name:
                return name
        return None
    except Exception:
        return None

# --- New helper: extract page slug by label (粉絲專頁 / Page) ---
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

        # 1) aria-label 指向粉專 / Page 的 anchor（絕對連結）
        m = re.search(
            r'<a[^>]+aria-label=["\'][^"\']*(?:粉絲專頁|Page)[^"\']*["\'][^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
            html, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return m.group(1)

        # 2) aria-label 指向粉專 / Page 的 anchor（相對連結）
        m = re.search(
            r'<a[^>]+aria-label=["\'][^"\']*(?:粉絲專頁|Page)[^"\']*["\'][^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
            html, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return m.group(1)

        # 3) 可見文字本身含有 粉絲專頁 / Page 的 anchor（較寬鬆）
        m = re.search(
            r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\'][^>]*>[^<]*(?:粉絲專頁|Page)[^<]*</a>',
            html, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return m.group(1)

        # 4) 相對連結 + 可見文字
        m = re.search(
            r'<a[^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\'][^>]*>[^<]*(?:粉絲專頁|Page)[^<]*</a>',
            html, flags=re.I | re.S
        )
        if m and good_pair(m.group(1), m.group(2) or ""):
            return m.group(1)

    except Exception:
        return None
    return None

# --- Helper: try upgrading profile.php?id=... to canonical page slug ---
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
        # 先抓頁面
        html_owner = None
        if storage_state:
            from .play_fetcher import fetch_with_playwright as _play_fetch
            html_owner = _play_fetch(owner_url, storage_state=storage_state)
        if not html_owner:
            from .fetcher import fetch_html as _fetch_html
            html_owner = _fetch_html(owner_url)
        if not html_owner:
            return None

        # 1) 通用 slug 抽取
        slug = _extract_owner_slug_from_html(html_owner)
        if slug:
            return f"https://m.facebook.com/{slug}"

        # 2) 備援掃描：絕對/相對錨點，並過濾非 owner 路徑
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

    # --- Generic owner backfill (non-share/r too) ---
    try:
        # A) Facebook post/group_post：若沒有 owner_url 或缺 page_followers/group_members，直接從 html 推回作者並補數字
        if type_tag in ("fb_post", "fb_group_post"):
            basic = data.get("basic") or {}
            # 先嘗試從目前 html 推 owner_url（slug / ownerProfileUrl / profile.php?id / reels_tab）
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
                # 3.5) 支援絕對連結：href="https://www.facebook.com/<slug>?..." 或 m.facebook.com，查詢字串可選
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
                # 3.6) 最後再試一次：通用 slug 抽取（含 JSON 轉義 / 絕對 / 相對）
                if not data["basic"].get("owner_url") and not slugG:
                    _slug_auto = _extract_owner_slug_from_html(html)
                    if _slug_auto:
                        data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_auto}"
            # 追加：從 aria-label="查看擁有者個人檔案" 的 <a> 直接推回 owner（常見於 Reels 版面）
            if not data["basic"].get("owner_url"):
                m = _reG.search(r'aria-label="查看擁有者個人檔案"[^>]+href="(/profile\.php\?[^"\\\']+)"', html)
                if not m:
                    # 英文備援（少見，但一併支援）
                    m = _reG.search(r'aria-label="View owner profile"[^>]+href="(/profile\.php\?[^"\\\']+)"', html)
                if m:
                    href = m.group(1).replace("&amp;", "&")
                    from urllib.parse import urljoin
                    owner_url = urljoin("https://m.facebook.com", href.split("&")[0])
                    data["basic"]["owner_url"] = owner_url
            # 3.6b) 新增：專抓 <a role="link" ...> 的頁名 anchor（Reels/新版 DOM）
            if not data["basic"].get("owner_url"):
                _slug_role = _extract_owner_slug_from_role_link(html)
                if _slug_role:
                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_role}"
            # 3.7) 再試一次：從 <a href="https://www.facebook.com/<slug>"> 直接抽
            if not data["basic"].get("owner_url") or "profile.php" in (data["basic"].get("owner_url") or ""):
                _slug_from_a = _extract_owner_from_anchors(html)
                if _slug_from_a:
                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_from_a}"

            # If owner_url is still a profile.php (common on reels), try upgrading it to a page slug
            try:
                cur_owner = data["basic"].get("owner_url")
                if cur_owner and "profile.php" in cur_owner and "/groups/" not in cur_owner:
                    upgraded = _upgrade_profile_to_page_slug(cur_owner, storage_state)
                    if upgraded:
                        data["basic"]["owner_url"] = upgraded
            except Exception:
                pass
            # 若已存在的 owner_url 指向通用/錯誤區（friends/marketplace/gaming 等）或為隨機 profile，
            # 而且 aria-label 有抓到另一個候選 owner，則覆蓋為候選 owner。
            if data["basic"].get("owner_url"):
                _owner_now = data["basic"]["owner_url"]
                # 標記不可信來源（容易被誤抓）
                _bad_roots = ("/friends", "/marketplace", "/gaming")
                _looks_bad = any(br in _owner_now for br in _bad_roots)
                # 如果頁面還有另一個 aria-label owner，拿來覆蓋
                m2 = _reG.search(r'aria-label="查看擁有者個人檔案"[^>]+href="(/profile\.php\?[^"\\\']+)"', html) or \
                     _reG.search(r'aria-label="View owner profile"[^>]+href="(/profile\.php\?[^"\\\']+)"', html)
                if (_looks_bad or _owner_now.endswith("id=0") or _owner_now.endswith("id=1")) and m2:
                    href2 = m2.group(1).replace("&amp;", "&")
                    from urllib.parse import urljoin
                    data["basic"]["owner_url"] = urljoin("https://m.facebook.com", href2.split("&")[0])

            # 若 HTML 有顯示名稱，先補上 owner_name（即便 owner_url 尚未升級）
            if not data.get("basic", {}).get("owner_name"):
                dn = _extract_owner_display_name(html or "")
                if dn:
                    data.setdefault("basic", {})["owner_name"] = dn

            # 若目前 owner_url 指向 profile.php（常見誤抓個人/錯頁），而頁面存在絕對的粉專連結
            # 例如：href="https://www.facebook.com/ETtoday?__tn__=-]C"，則優先改用 slug 版本
            try:
                import re as _reABS
                cur_owner = data["basic"].get("owner_url")
                need_fix = bool(cur_owner and "profile.php" in cur_owner and "/groups/" not in cur_owner)
                # 或者 followers 尚未取得也可以嘗試修正
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
            # 若已升級 owner_url，補 owner_name
            if not data.get("basic", {}).get("owner_name"):
                # 升級後再嘗試從新版頁面取名稱
                try:
                    html_owner2 = fetch_html(owner_for_follow)
                except Exception:
                    html_owner2 = None
                dn2 = _extract_owner_display_name(html_owner2 or "")
                if dn2:
                    data.setdefault("basic", {})["owner_name"] = dn2
            if owner_for_follow and (data["basic"].get("page_followers") is None and "/groups/" not in owner_for_follow):
                # 粉專/個人：補 followers
                html_owner = None
                if storage_state:
                    from .play_fetcher import fetch_with_playwright as _play_fetch
                    html_owner = _play_fetch(owner_for_follow, storage_state=storage_state)
                if not html_owner:
                    html_owner = fetch_html(owner_for_follow)
                # If owner is a profile.php page, try to upgrade it to a real page slug found on that page
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
                                # upgrade to the canonical page slug and refetch that page
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
                        # Extra fallback: grab visible counters like "有 12,345 位追蹤者" or similar header counters
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
                # 社團：補 members
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

        # B) Instagram post：若缺 owner_followers，從 html 找作者帳號再抓 profile
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

    # --- share/r|share/p 補強：若 basic.owner_url 尚未取得，追最終 permalink 再解析一次 ---
    try:
        is_fb_share = "facebook.com/share/" in (rewritten_url or url)
        if type_tag in ("fb_post", "fb_group_post") and is_fb_share:
            basic = data.get("basic") or {}
            owner_url = basic.get("owner_url")
            if (not owner_url) or (basic.get("page_followers") is None):
                storage_state = os.getenv("FBIG_STORAGE_STATE") or None
                # 1) 先用 Playwright 嘗試轉址；失敗再用 requests
                final_u = (
                    _resolve_final_url_playwright(rewritten_url or url, storage_state=storage_state)
                    or _resolve_final_url_requests(rewritten_url or url)
                )
                # 仍未取得 → 嘗試直接從目前 HTML 解析最終 permalink
                if (not final_u) or ("facebook.com/share/" in final_u):
                    # 盡可能使用剛抓到的 html 來源來抽 permalink
                    html_source = html if isinstance(html, str) else ""
                    extracted = _extract_final_permalink_from_html(html_source)
                    if extracted:
                        final_u = extracted

                # 若 final_u 仍缺，嘗試直接抽 owner 數字 ID 組成 owner_url
                if (not final_u) and (not owner_url):
                    owner_id = _extract_owner_id_from_html(html_source)
                    if owner_id:
                        derived_owner = f"https://m.facebook.com/profile.php?id={owner_id}"
                        data.setdefault("basic", {})["owner_url"] = derived_owner
                        # 直接補 owner followers/members
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
                    # 改成 m.facebook 版本以提升未登入可視性
                    final_u = final_u.replace("https://www.facebook.com", "https://m.facebook.com")

                    # 2a) 嘗試從最終 permalink 直接推回 owner（slug 或數字 id）
                    import re as _re
                    derived_owner = None
                    try:
                        # /<slug>/posts/<id>
                        m = _re.search(r"https://m\.facebook\.com/([A-Za-z0-9._-]+)/posts/\d+", final_u)
                        if m:
                            derived_owner = f"https://m.facebook.com/{m.group(1)}"
                        # /<slug>/videos/<id>
                        if not derived_owner:
                            m = _re.search(r"https://m\.facebook\.com/([A-Za-z0-9._-]+)/videos/\d+", final_u)
                            if m:
                                derived_owner = f"https://m.facebook.com/{m.group(1)}"
                        # story.php?id=<digits>
                        if not derived_owner:
                            m = _re.search(r"https://m\.facebook\.com/story\.php\?[^#]*\bid=(\d+)", final_u)
                            if m:
                                derived_owner = f"https://m.facebook.com/profile.php?id={m.group(1)}"
                        # permalink.php?story_fbid=...&id=<digits>
                        if not derived_owner:
                            m = _re.search(r"https://m\.facebook\.com/permalink\.php\?[^#]*\bid=(\d+)", final_u)
                            if m:
                                derived_owner = f"https://m.facebook.com/profile.php?id={m.group(1)}"
                        # groups/<slug>/posts/<id> → 這屬於社團；若遇到，先填社團 owner
                        if not derived_owner:
                            m = _re.search(r"https://m\.facebook\.com/groups/([A-Za-z0-9._-]+)/posts/\d+", final_u)
                            if m:
                                derived_owner = f"https://m.facebook.com/groups/{m.group(1)}"
                    except Exception:
                        pass

                    # 若成功推得 owner，直接寫入並嘗試補粉專追蹤數/社團成員數
                    if derived_owner:
                        data.setdefault("basic", {})["owner_url"] = derived_owner
                        # 也盡量補上顯示名稱
                        if not data.get("basic", {}).get("owner_name"):
                            dn = _extract_owner_display_name(html or "")
                            if dn:
                                data.setdefault("basic", {})["owner_name"] = dn
                        # 將 profile.php 形式的 owner_url 嘗試升級成 slug
                        try:
                            curr = data.get("basic", {}).get("owner_url")
                            upgraded = _upgrade_profile_to_page_slug(curr, storage_state)
                            if upgraded:
                                data["basic"]["owner_url"] = upgraded
                        except Exception:
                            pass
                        # 針對粉專/個人頁補 followers；社團則補 members
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
                                        pass  # 中文欄位會在下方統一重建
                            else:
                                        page_basic = parse_fb_page_basic(html_owner)
                                        if page_basic.get("followers") is not None:
                                            data["basic"]["page_followers"] = page_basic["followers"]

                                        # Fallback 1：HTML 直接抽（支援 JSON 鍵 + 單位）
                                        if data["basic"].get("page_followers") is None:
                                            n = _extract_followers_from_html(html_owner)
                                            if isinstance(n, int):
                                                data["basic"]["page_followers"] = n

                                        # Fallback 2：換 owner 細節頁再抓一次
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

                    # 2) 抓最終 URL 的 HTML（登入優先）
                    html2 = None
                    if storage_state:
                        from .play_fetcher import fetch_with_playwright as _play_fetch
                        html2 = _play_fetch(final_u, storage_state=storage_state)
                    if not html2:
                        html2 = fetch_html(final_u)
                    if html2:
                        # 3) 再跑一次 post 解析，期待拿到 owner_url
                        try:
                            basic2 = parse_fb_post_basic(html2)
                            if basic2.get("owner_url"):
                                data["basic"]["owner_url"] = basic2["owner_url"]

                            # Fallback A: 若 basic2 沒給 owner_url，嘗試從 html2 直接抽 owner 數字 ID
                            if not data["basic"].get("owner_url"):
                                owner_id2 = _extract_owner_id_from_html(html2)
                                if owner_id2:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/profile.php?id={owner_id2}"

                            # Fallback B: Reel/Photo/Watch 版面：從 slug 型連結推回 owner
                            if not data["basic"].get("owner_url"):
                                import re as _re2
                                slug = None
                                # 1) /<slug>/reels/...
                                m = _re2.search(r'href="/([A-Za-z0-9._-]+)/reels/', html2)
                                if m:
                                    slug = m.group(1)
                                # 2) /<slug>?... 常見於作者頭像/名稱連結
                                if not slug:
                                    m = _re2.search(r'href="/([A-Za-z0-9._-]+)\?[^"]*ref=content_permalink', html2)
                                    if m:
                                        slug = m.group(1)
                                # 3) JSON 內的 ownerProfileUrl
                                if not slug:
                                    m = _re2.search(r'"ownerProfileUrl"\s*:\s*"https:\\/\\/m\\.facebook\\.com\\/([^"\\]+)"', html2)
                                    if m:
                                        slug = m.group(1).split("\\/")[0]
                                # 3.5) 支援絕對連結：href="https://www.facebook.com/<slug>?..." 或 m.facebook.com，查詢字串可選
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
                                # 3.6) 再加一層通用 slug 抽取（含 JSON 轉義 / 絕對 / 相對）
                                if not slug and not data["basic"].get("owner_url"):
                                    _slug_auto2 = _extract_owner_slug_from_html(html2)
                                    if _slug_auto2:
                                        slug = _slug_auto2
                                if slug and slug.lower() not in ("share", "reel", "watch", "photo.php", "story.php", "permalink.php", "marketplace", "gaming", "friends"):
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{slug}"
                            # 追加：從 aria-label="查看擁有者個人檔案" 的 <a> 直接推回 owner（share/r → 最終頁面）
                            if not data["basic"].get("owner_url"):
                                m = _re2.search(r'aria-label="查看擁有者個人檔案"[^>]+href="(/profile\.php\?[^"\\\']+)"', html2)
                                if not m:
                                    m = _re2.search(r'aria-label="View owner profile"[^>]+href="(/profile\.php\?[^"\\\']+)"', html2)
                                if m:
                                    href = m.group(1).replace("&amp;", "&")
                                    from urllib.parse import urljoin
                                    owner_url = urljoin("https://m.facebook.com", href.split("&")[0])
                                    data["basic"]["owner_url"] = owner_url

                            # 覆蓋策略：若目前 owner_url 仍為 None 或者 followers 還是抓不到，
                            # 而 html2 的 aria-label 提供了更可信的 profile.php?id=XXXX，則用它覆蓋。
                            need_override = (data["basic"].get("page_followers") is None)
                            if need_override:
                                m_override = _re2.search(r'aria-label="查看擁有者個人檔案"[^>]+href="(/profile\.php\?[^"\\\']+)"', html2) or \
                                              _re2.search(r'aria-label="View owner profile"[^>]+href="(/profile\.php\?[^"\\\']+)"', html2)
                                if m_override:
                                    href_ov = m_override.group(1).replace("&amp;", "&")
                                    from urllib.parse import urljoin
                                    owner_candidate = urljoin("https://m.facebook.com", href_ov.split("&")[0])
                                    cur = data["basic"].get("owner_url")
                                    # 只有在目前 owner 不可信或缺 followers 時才覆蓋
                                    _bad_roots = ("/friends", "/marketplace", "/gaming")
                                    if (cur is None) or any(br in (cur or "") for br in _bad_roots):
                                        data["basic"]["owner_url"] = owner_candidate

                            # 若 owner_url 目前仍為 profile.php 或 followers 尚未取得，
                            # 嘗試以 html2 中的絕對連結（https://www.facebook.com/<slug>?... 或 m.facebook.com，查詢字串可選）矯正
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

                            # 額外備援：再掃一次絕對/相對錨點，只要是 /<slug> 或 https://(www|m).facebook.com/<slug> 就採用，
                            # 但排除常見內部路徑，並忽略指向貼文/reels 等的第二段。
                            if not data["basic"].get("owner_url"):
                                import re as _reANY
                                bad_first = {"share","reel","watch","photo.php","story.php","permalink.php","marketplace","gaming","friends","groups",
                                            "profile.php","data","privacy_sandbox","help","settings","policy","login","pages"}
                                allowed_next = {"","reels","posts","videos","photos","about","pg","timeline"}
                                # 1) 絕對
                                m = _reANY.search(
                                    r'<a[^>]+href=["\']https?://(?:www|m)\.facebook\.com/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
                                    html2, flags=_reANY.I | _reANY.S
                                )
                                if m:
                                    cand, nxt = m.group(1), (m.group(2) or "").lower()
                                    if cand.lower() not in bad_first and nxt in allowed_next:
                                        data["basic"]["owner_url"] = f"https://m.facebook.com/{cand}"
                                # 2) 相對
                                if not data["basic"].get("owner_url"):
                                    m = _reANY.search(
                                        r'<a[^>]+href=["\']/([A-Za-z0-9._-]+)(?:/([A-Za-z0-9._-]+))?(?:\?[^"\']*)?["\']',
                                        html2, flags=_reANY.I | _reANY.S
                                    )
                                    if m:
                                        cand, nxt = m.group(1), (m.group(2) or "").lower()
                                        if cand.lower() not in bad_first and nxt in allowed_next:
                                            data["basic"]["owner_url"] = f"https://m.facebook.com/{cand}"

                            # 4) 若還沒有 page_followers，就去 owner_url 抓粉專/社團數字
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
                            # 3.7a) 若 owner 仍是 profile.php，嘗試透過含「粉絲專頁 / Page」語意的錨點來升級為粉專 slug
                            cur_owner_tmp = data["basic"].get("owner_url")
                            if (not cur_owner_tmp) or ("profile.php" in cur_owner_tmp):
                                _slug_by_label = _extract_page_slug_by_label(html2)
                                if not _slug_by_label:
                                    _slug_by_label = _extract_page_slug_by_label(html)  # 也嘗試從第一次抓到的 html 補救
                                if _slug_by_label:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_by_label}"

                            # 3.7a-rl) 新增：從 <a role="link" ...> 抽出粉專 slug（優先於一般 anchor）
                            if not data["basic"].get("owner_url"):
                                _slug_role2 = _extract_owner_slug_from_role_link(html2) or _extract_owner_slug_from_role_link(html)
                                if _slug_role2:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_role2}"
                            # 3.7b) 直接從 html2 的 <a href="https://www.facebook.com/<slug>"> 抽出 owner
                            if not data["basic"].get("owner_url") or "profile.php" in (data["basic"].get("owner_url") or ""):
                                _slug_from_a2 = _extract_owner_from_anchors(html2)
                                if _slug_from_a2:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_from_a2}"

                            # 3.8) 最終強制修正：
                            # 若 owner_url 仍為 profile.php（常見於 Reels 頁將作者導向個人檔案），
                            # 但頁面中存在明確的粉專 slug 連結（如 https://www.facebook.com/ETtoday），
                            # 則直接覆蓋為 slug 形式，提升後續追蹤數解析成功率。
                            cur_owner = data["basic"].get("owner_url")
                            if cur_owner and "profile.php" in cur_owner:
                                _slug_final = _extract_owner_from_anchors(html2) or _extract_owner_from_anchors(html)
                                if _slug_final:
                                    data["basic"]["owner_url"] = f"https://m.facebook.com/{_slug_final}"
                                    cur_owner = data["basic"]["owner_url"]

                            # 若 followers 仍為空，使用修正後的 owner_url 再補抓一次粉專追蹤數
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
                    # 更新 meta：記錄實際解析的最終 URL
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