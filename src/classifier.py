def classify(url):
    if "facebook" in url:
        return "facebook"
    elif "instagram" in url:
        return "instagram"
    else:
        return "unknown"