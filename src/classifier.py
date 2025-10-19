def classify(url):
    url = url.lower()
    
    if "facebook.com/groups/" in url:
        return "fb_group"
    elif "facebook.com" in url and "/posts/" not in url:
        return "fb_post"
    elif "facebook.com" in url:
        return "fb_page"
    elif "instagram.com/p/" in url:
        return "ig_post"
    elif "instagram.com" in url:
        return "ig_profile"
    else:
        return "unknown"