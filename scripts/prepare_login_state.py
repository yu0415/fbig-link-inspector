from playwright.sync_api import sync_playwright

def main():
    print("請在開啟的瀏覽器中登入 Facebook 或 Instagram，登入完回到這裡按 Enter。")
    with sync_playwright() as p:
        browser = p.chromium,launch(headless=False)
        context = browser.new_context()
        page = context.new_context()
        page.goto("https://www.facebook.com/login")
        input("登入完成請按Enter")
        context.storage_state(path="state.json")
        context.close()
        browser.close()
    print("登入狀態已儲存在stat.json")

if __name__ =="__main":
    main()