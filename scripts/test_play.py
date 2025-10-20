import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.play_fetcher import fetch_with_playwright

url = "https://www.instagram.com/nasa/"
html = fetch_with_playwright(url)

print("HTML長度", len(html) if html else "Fetch failed")