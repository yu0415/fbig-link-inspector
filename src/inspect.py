from .classifier import classify
from .fetcher import fetch_html
from .parser import parse_basic_meta
import time

def inspect_url(url: str) -> dict:
    t0 = time.time()
    type_tag = classify(url)
    html = fetch_html(url)

    if not html:
        return {
            "status": "error",
            "type": type_tag,
            "data": None,
            "meta": {
                "duration_ms": int((time.time() - t0) * 1000),
                "fetched_with": "requests",
            },
            "error": "fetch_failed",
        }

    data = parse_basic_meta(html)
    return {
        "status": "ok",
        "type": type_tag,
        "data": data,
        "meta": {
            "duration_ms": int((time.time() - t0) * 1000),
            "fetched_with": "requests",
        },
        "error": None,
    }