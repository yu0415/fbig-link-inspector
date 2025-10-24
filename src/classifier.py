import re

def classify(url: str) -> str:
    """
    Robust URL classifier for FB/IG.
    Returns one of:
      fb_page | fb_post | fb_group | fb_group_post | ig_profile | ig_post | unknown
    """
    if not url:
        return "unknown"

    u = url.strip()
    ul = u.lower()

    # --- fb.watch short domain ---
    if ul.startswith("https://fb.watch") or ul.startswith("http://fb.watch"):
        return "fb_post"

    # --- Facebook ---
    if "facebook.com" in ul:
        # Path after domain
        path = re.split(r"facebook\.com", ul, maxsplit=1)[-1]
        path = re.split(r"[?#]", path, maxsplit=1)[0]
        if not path.startswith("/"):
            path = "/" + path
        path = re.sub(r"/+\Z", "", path or "")

        # Groups
        if re.search(r"^/groups/[^/?#]+$", path, flags=re.IGNORECASE):
            return "fb_group"
        if re.search(r"^/groups/[^/?#]+/posts?/", path, flags=re.IGNORECASE):
            return "fb_group_post"

        # Post-like patterns (order matters)
        post_patterns = [
            r"^/share/(?:r|p)/",                  # share shortlinks
            r"^/watch/",                           # watch
            r"^/reel/",                            # reels
            r"^/photo\.php",                       # photo.php
            r"^/permalink\.php",                   # permalink.php
            r"^/[^/]+/(?:posts|videos|photos)/",   # /<page>/(posts|videos|photos)/
        ]
        for pat in post_patterns:
            if re.search(pat, path, flags=re.IGNORECASE):
                return "fb_post"

        # Single-segment page like /NASA
        if re.search(r"^/[^/?#]+$", path, flags=re.IGNORECASE) and not re.search(
            r"^/(login|share|watch|reel|permalink|photo\.php)\b", path, flags=re.IGNORECASE
        ):
            return "fb_page"

        return "unknown"

    # --- Instagram ---
    if "instagram.com" in ul:
        path = re.split(r"instagram\.com", ul, maxsplit=1)[-1]
        path = re.split(r"[?#]", path, maxsplit=1)[0]
        if not path.startswith("/"):
            path = "/" + path
        path = re.sub(r"/+\Z", "", path or "")

        # Post types: /p/<id>/, /reel/<id>/, /tv/<id>/
        if re.search(r"^/(?:p|reel|tv)/[^/?#]+$", path, flags=re.IGNORECASE):
            return "ig_post"

        # Profile: exactly one segment (exclude known non-profile namespaces)
        if re.search(r"^/[^/?#]+$", path, flags=re.IGNORECASE):
            if not re.search(
                r"^/(explore|stories|reels|reel|p|tv|accounts|about|developer|directory|topics|help|privacy|terms|blog|press|api|oauth)\b",
                path,
                flags=re.IGNORECASE,
            ):
                return "ig_profile"

        return "unknown"

    return "unknown"