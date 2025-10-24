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

    # Fallback 2: look into inline JSON in <script> tags
    if followers is None:
        json_number = None
        for sc in soup.find_all("script"):
            s = sc.string or sc.get_text()
            if not s:
                continue
            # common page counters used by FB
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

    # Decide source hint
    source_hint = "text"
    try:
        source_hint = source  # may be set to "meta" or "json" above
    except NameError:
        pass

    basic = _blank_basic(note=None if followers is not None else "not_found", source_hint=source_hint)
    basic["followers"] = followers
    return basic

# ---------- FB: Page Post ----------

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