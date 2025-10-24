import re

def normalize_number(text: str):
    """將中英文混合的數字格式化成整數，例如 1.2萬 → 12000、3.4M → 3400000"""
    if not text:
        return None
    text = text.strip()
    text = text.replace(",", "").replace("+", "")

    m = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*(萬|億|k|K|m|M)?", text)
    if not m:
        return None

    num = float(m.group(1).replace(",", "").replace(" ", ""))
    unit = m.group(2)

    if unit in ("k", "K"):
        num *= 1_000
    elif unit in ("m", "M"):
        num *= 1_000_000
    elif unit == "萬":
        num *= 10_000
    elif unit == "億":
        num *= 100_000_000

    return int(num)