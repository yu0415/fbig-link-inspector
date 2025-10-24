from playwright.sync_api import sync_playwright

def main():
    print("請在開啟的瀏覽器中登入 Facebook 或 Instagram，登入完回到這裡按 Enter。")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.facebook.com/login")
        input("登入完成請按 Enter 後繼續...")
        context.storage_state(path="state.json")
        context.close()
        browser.close()
    print("登入狀態已儲存在 state.json")

if __name__ == "__main__":
    main()