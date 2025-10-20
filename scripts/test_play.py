from src.play_fetcher import fetch_with_playwright 

url = "https://www.instagram.com/nasa/"

html = fetcher_with_playwright(url)

print("HTML長度", len(html))