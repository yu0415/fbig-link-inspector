from bs4 import BeautifulSoup
import re
from typing import Optional, Dict, Any
from .utils import normalize_number

# ---------- helpers ----------

def _blank_basic(note: Optional[str] = None, source_hint: str = "text") -> Dict[str, Any]:
    return {
        "followers": None,
        "members": None,
        "likes": None,
        "shares": None,
        "page_followers": None,
        "group_members": None,
        "owner_followers": None,
        "source_hint": source_hint,
        "note": note,
    }

def _search_number_patterns(text: str, patterns) -> Optional[int]:
    """Try a list of regex patterns, return first normalized number found."""
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return normalize_number(m.group(1))
    return None

# ---------- FB: Page ----------

def parse_fb_page_basic(html: str) -> dict:
    """
    解析 FB 粉絲專頁追蹤數
    目標欄位：basic.followers
    """
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True)

    followers = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*(?:位)?追蹤者",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*followers",
            r"追蹤者\s*([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)",
        ],
    )

    # Fallback 1: meta[name="description"]
    if followers is None:
        desc = None
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            desc = meta_desc["content"]
        if desc:
            f2 = _search_number_patterns(
                desc,
                [
                    r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*(?:位)?追蹤者",
                    r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*followers",
                ],
            )
            if f2 is not None:
                followers = f2
                source = "meta"
            else:
                source = "text"
        else:
            source = "text"
            
    if followers is None:
        json_number = None
        for sc in soup.find_all("script"):
            s = sc.string or sc.get_text()
            if not s:
                continue
            
            m = re.search(r'"followers_count"\s*:\s*([0-9]+)', s)
            if not m:
                m = re.search(r'"page_fan_count"\s*:\s*([0-9]+)', s)
            if not m:
                m = re.search(r'"page_likers_count"\s*:\s*([0-9]+)', s)
            if not m:
                m = re.search(r'"subscriber_count"\s*:\s*([0-9]+)', s)
            if m:
                try:
                    json_number = int(m.group(1))
                    break
                except Exception:
                    pass
        if json_number is not None:
            followers = json_number
            source = "json"
            
    source_hint = "text"
    try:
        source_hint = source  # may be set to "meta" or "json" above
    except NameError:
        pass

    basic = _blank_basic(note=None if followers is not None else "not_found", source_hint=source_hint)
    basic["followers"] = followers
    return basic



def parse_fb_post_basic(html: str) -> dict:
    """
    解析 FB 粉專貼文：讚數 / 分享數 + 所屬粉專追蹤數（若頁面可見）
    目標欄位：basic.likes, basic.shares, basic.page_followers
    """
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True)

    likes = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*(?:個)?讚",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*likes?",
        ],
    )
    shares = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*次分享",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*shares?",
        ],
    )
    page_followers = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*(?:位)?追蹤者",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*followers",
        ],
    )

    note = None if any([likes, shares, page_followers]) else "not_found"
    basic = _blank_basic(note=note, source_hint="text")
    basic["likes"] = likes
    basic["shares"] = shares
    basic["page_followers"] = page_followers
    return basic

# ---------- FB: Post (Enhanced for share/r/p) ----------

def parse_fb_post_basic(html: str) -> dict:
    """
    強化版：解析 FB 貼文頁（如 /share/r/... 或 /share/p/...）的讚數、分享數與所屬粉專追蹤數。
    目標欄位：basic.likes, basic.shares, basic.page_followers
    """
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True)

    likes = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*(?:個)?讚",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*likes?",
        ],
    )
    shares = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*次分享",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*shares?",
        ],
    )
    page_followers = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*(?:位)?追蹤者",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*followers",
            r"追蹤者\s*([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)",
        ],
    )

    source_hint = "text"
    found_by_text = any([likes, shares, page_followers])

    # 若純文字沒找到，嘗試從 script 標籤內 JSON 結構提取
    if not found_by_text:
        for sc in soup.find_all("script"):
            s = sc.string or sc.get_text()
            if not s:
                continue
            # 嘗試尋找 like_count
            if likes is None:
                m = re.search(r'"like_count"\s*:\s*([0-9]+)', s)
                if m:
                    try:
                        likes = int(m.group(1))
                    except Exception:
                        pass
            if shares is None:
                m = re.search(r'"share_count"\s*:\s*([0-9]+)', s)
                if m:
                    try:
                        shares = int(m.group(1))
                    except Exception:
                        pass
            # --- Deep JSON patterns (e.g., __bbox / feedbackContext) ---
            # 1) feedback / __bbox deep JSON with nested counts
            if likes is None:
                m = re.search(r'"feedback"[\s\S]*?"reaction_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)', s)
                if not m:
                    m = re.search(r'"__bbox"[\s\S]*?"reaction_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)', s)
                if m:
                    try:
                        likes = int(m.group(1))
                    except Exception:
                        pass

            if shares is None:
                m = re.search(r'"feedback"[\s\S]*?"share_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)', s)
                if not m:
                    m = re.search(r'"__bbox"[\s\S]*?"share_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)', s)
                if not m:
                    m = re.search(r'"shares"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)', s)
                if m:
                    try:
                        shares = int(m.group(1))
                    except Exception:
                        pass
            # like_count may appear as {"like_count":{"count":123}} or {"reaction_count":{"count":123}}
            if likes is None:
                m = re.search(r'"like_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)', s)
                if not m:
                    m = re.search(r'"reaction_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)', s)
                if m:
                    try:
                        likes = int(m.group(1))
                    except Exception:
                        pass
            # share_count may appear as {"share_count":{"count":45}} or {"shares":{"count":45}}
            if shares is None:
                m = re.search(r'"share_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)', s)
                if not m:
                    m = re.search(r'"shares"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)', s)
                if m:
                    try:
                        shares = int(m.group(1))
                    except Exception:
                        pass
            # 嘗試尋找 page_followers
            if page_followers is None:
                # 常見欄位
                m = re.search(r'"followers_count"\s*:\s*([0-9]+)', s)
                if not m:
                    m = re.search(r'"page_fan_count"\s*:\s*([0-9]+)', s)
                if not m:
                    m = re.search(r'"page_likers_count"\s*:\s*([0-9]+)', s)
                if not m:
                    m = re.search(r'"subscriber_count"\s*:\s*([0-9]+)', s)
                if m:
                    try:
                        page_followers = int(m.group(1))
                    except Exception:
                        pass
            # 若三者皆有就不用再 loop
            if likes is not None and shares is not None and page_followers is not None:
                break
        if any([likes, shares, page_followers]):
            source_hint = "json"

    # Fallback: aria-label text counts from visible buttons (localized)
    if likes is None or shares is None:
        try:
            nodes = soup.find_all(attrs={"aria-label": True})
            for n in nodes:
                label = n.get("aria-label") or ""
                if likes is None and re.search(r"(讚|likes?)", label, re.IGNORECASE):
                    m = re.search(r"([0-9][0-9.,]*)", label)
                    if m:
                        likes = normalize_number(m.group(1))
                if shares is None and re.search(r"(分享|shares?)", label, re.IGNORECASE):
                    m = re.search(r"([0-9][0-9.,]*)", label)
                    if m:
                        shares = normalize_number(m.group(1))
        except Exception:
            pass
    if any([likes, shares]) and source_hint == "text":
        # If we only found via aria-labels, treat as 'json' equivalent richness
        source_hint = "json"

    # Final-pass: scan whole HTML for more JSON patterns (robust against script splits)
    if likes is None:
        for pat in [
            r'"reaction_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)',
            r'"like_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)',
            r'"likers"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)',
            r'"like_count"\s*:\s*([0-9]+)',
        ]:
            m = re.search(pat, html, flags=re.IGNORECASE)
            if m:
                try:
                    likes = int(m.group(1))
                    source_hint = "json"
                    break
                except Exception:
                    pass
    if shares is None:
        for pat in [
            r'"share_count"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)',
            r'"shares"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)',
            r'"reshares"\s*:\s*\{\s*"count"\s*:\s*([0-9]+)',
            r'"share_count"\s*:\s*([0-9]+)',
        ]:
            m = re.search(pat, html, flags=re.IGNORECASE)
            if m:
                try:
                    shares = int(m.group(1))
                    source_hint = "json"
                    break
                except Exception:
                    pass
    if page_followers is None:
        for pat in [
            r'"followers_count"\s*:\s*([0-9]+)',
            r'"page_fan_count"\s*:\s*([0-9]+)',
            r'"page_likers_count"\s*:\s*([0-9]+)',
            r'"subscriber_count"\s*:\s*([0-9]+)',
        ]:
            m = re.search(pat, html, flags=re.IGNORECASE)
            if m:
                try:
                    page_followers = int(m.group(1))
                    if source_hint == "text":
                        source_hint = "json"
                    break
                except Exception:
                    pass

    note = None if any([likes, shares, page_followers]) else "not_found"
    basic = _blank_basic(note=note, source_hint=source_hint)
    basic["likes"] = likes
    basic["shares"] = shares
    basic["page_followers"] = page_followers
    return basic

# ---------- FB: Group ----------

def parse_fb_group_basic(html: str) -> dict:
    """
    解析 FB 社團主頁：成員數
    目標欄位：basic.members
    """
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True)

    members = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*(?:位)?成員",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*members",
        ],
    )

    basic = _blank_basic(note=None if members is not None else "not_found", source_hint="text")
    basic["members"] = members
    return basic

# ---------- FB: Group Post ----------

def parse_fb_group_post_basic(html: str) -> dict:
    """
    解析 FB 社團貼文：讚數 / 分享數 + 社團成員數（若頁面可見）
    目標欄位：basic.likes, basic.shares, basic.group_members
    """
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True)

    likes = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*(?:個)?讚",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*likes?",
        ],
    )
    shares = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*次分享",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*shares?",
        ],
    )
    group_members = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*(?:位)?成員",
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*members",
        ],
    )

    note = None if any([likes, shares, group_members]) else "not_found"
    basic = _blank_basic(note=note, source_hint="text")
    basic["likes"] = likes
    basic["shares"] = shares
    basic["group_members"] = group_members
    return basic

# ---------- IG: Profile ----------

def parse_ig_profile_basic(html: str) -> dict:
    """
    解析 IG 帳號主頁：追蹤數
    目標欄位：basic.followers
    備註：未登入時常不可見；若抓不到回 note='requires_login'
    """
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True)

    followers = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*followers",
            r"追蹤者?\s*([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)",
        ],
    )

    note = None if followers is not None else "requires_login"
    basic = _blank_basic(note=note, source_hint="text")
    basic["followers"] = followers
    return basic

# ---------- IG: Post ----------

def parse_ig_post_basic(html: str) -> dict:
    """
    解析 IG 貼文：讚數（若作者未隱藏）/ 所屬帳號追蹤數（若可見）
    目標欄位：basic.likes, basic.owner_followers
    備註：未登入時多半不可見；抓不到以 note='requires_login' 或 'hidden'
    """
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True)

    likes = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*likes?",
            r"讚\s*([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)",
        ],
    )
    owner_followers = _search_number_patterns(
        text,
        [
            r"([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)\s*followers",
            r"追蹤者?\s*([0-9][0-9.,]*\s*(?:[kKmM]|萬|億)?)",
        ],
    )

    note = None
    if likes is None and owner_followers is None:
        note = "requires_login"
    elif likes is None:
        note = "hidden"

    basic = _blank_basic(note=note, source_hint="text")
    basic["likes"] = likes
    basic["owner_followers"] = owner_followers
    return basic