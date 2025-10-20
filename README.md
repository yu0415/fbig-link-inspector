 # 20251018 取得 FB / IG 連結資訊 (Alex) - 實現任務
 
>**發佈任務** : https://hackmd.io/@eric35551/BywW7yeAex
'''
> # 20251017 取得FB/IG連結資訊(Alex) - 任務敘述


>需要製作一個程式，在輸入某FB或IG的連結後，可辨別(取得)該連結的「連結類型」及「基礎資訊」，並回傳前端。
需注意並符合以下要求：
>1. 需大量測試各種連結形式，如：「FB及IG外面網站(非FB/IG平台網域)生成的短連結」、「FB及IG電腦瀏覽器上方的url」、「FB及IG手機/電腦分享連結」、…等。
>2. 請求後，時間需於 5 秒內回傳，盡量不超過5秒。

'''
**工作主題** : 取得FB/IG連結資訊（Alex）

**成果紀錄**  

 **GitHub 相關連結**
 
 **https://github.com/yu0415/fbig-link-inspector**

Ⅰ. **工作日期 / 工作目標（進度或欲解決之問題） / 行業別 / 作業過程與方法** 

工作日期：2025/10/18－2025/10/19
工作目標：
建立能於輸入任意 Facebook / Instagram 連結後，自動判斷「連結類型」與「基礎資訊」的程式模組。
核心要求：
1️⃣ 支援多種連結格式（短連結、分享連結、外部嵌入、個人/粉專頁面）
2️⃣ 回傳結果需在 5 秒內完成
3️⃣ 程式需模組化、可快速整合 API
行業別：社群媒體資料分析 / 網路爬蟲自動化

**2025/10/18**

1. 建立 GitHub 專案並初始化目錄結構（src/, tests/）。
2. 設定 .gitignore、README.md、requirements.txt。
3. 撰寫 fetcher.py 初版模組，用於安全擷取 HTML。
4. 建立 parser.py 與 inspect.py 的基本框架。
5. 驗證 Python 3.7 環境相容性並修正 import path 問題。
6. 首次 push 至 GitHub，commit 訊息：init: project scaffold。

**2025/10/19**

1. 測試 fetch_html() 函式於多種 Facebook 連結型態。
2. 驗證短連結（fb.me, l.facebook.com）與正式網址轉址行為。
3. 修正 import 錯誤（fetcher_html → fetch_html）。
4. 新增 timeout 與時間紀錄（確保回傳 < 5 秒）。
5. 改善除錯資訊（print more details）。
6. 建立單元測試 test_classifier.py 並通過初步測試。

**2025/10/20**
1.	新增 src/play_fetcher.py（Playwright / Chromium headless）做動態抓取，成功取得大體量 HTML（>1.3MB）。
2.	在 inspect.py 串接 requests → Playwright fallback：fetch_html() 失敗時自動改用 fetch_with_playwright()。
3.	inspect.py 新增/修正診斷欄位：meta.fetched_with（requests / playwright）、duration_ms、was_rewritten、rewritten_url。
4.	Facebook 連結自動 改寫為 m.facebook.com（page / post / group），有效降低 login wall 影響並提升成功率。
5.	classifier.py 補強 IG Reels 規則：instagram.com/reel/ → ig_post（避免誤判為 profile）；統一以 lowercase 比對。
6.	parser.py 驗證 OG 解析流程，保留 <title> / meta[name="description"] 等 fallback（IG 未登入時 og:* 可能為 None）。
7.	新增/整理測試腳本 scripts/test_play.py：先抓後 parse，列印 HTML 長度與 meta，並修正 sys.path 以便從專案根執行。
8.	以真實連結驗證：NASA/UNICEF/WHO/Google/Microsoft 粉專、fb.watch 影片、公開社團、IG profile/post/reel；FB 全部成功回傳 og，IG 在未登入情境下 og:* 多為 None（預期）。
9.	更新 requirements.txt（加入 playwright 等相依），並完成 Git 提交與推送（保留可重現環境）。
10.	彙整 HackMD「成果發布模板」與「Parser × Fallback 詳解」章節（含決策流程、日誌範例、失敗模式與診斷欄位），作為日後迭代與交付依據。

**（三）使用之程式方法**

requests：HTTP 請求與 timeout 控制
BeautifulSoup：HTML 結構解析
urllib.parse：網域與參數解析
time：紀錄執行時間
pytest：單元測試框架

**（四）使用工具**

macOS (M1)
Python 3.7.9
Visual Studio Code
GitHub
HackMD

**（五）完成事項**
1. ✅ 建立專案骨架
2. ✅ 實作 fetch_html 函式
3. ✅ 測試短連結轉址行為
4. ✅ 建立測試結構與 README
5. ✅ 控制回傳時間小於 5 秒 

**（六）未解決問題**

1. 尚未完成完整的連結分類邏輯（FB/IG/外部）
2. 尚未整合 API 輸出格式
3. 待補代理 IP 與 User-Agent 池

**（七）工作計畫**

2025/10/20 完成 classifier.py 主邏輯（實作連結分類功能，能正確辨識 Facebook、Instagram、外部連結

Ⅱ. **程式檔案名稱與存放路徑**

├─ fbig-link-inspector/
│　├─ src/
│　│　├─ __init__.py
│　│　├─ classifier.py
│　│　├─ fetcher.py
│　│　├─ inspect.py
│　│　├─ parser.py
│　│　└─ utils.py
│　│
│　├─ tests/
│　│　├─ __init__.py
│　│　└─ test_classifier.py
│　│
│　├─ .gitignore
│　├─ README.md
│　└─ requirements.txt


Ⅲ. **程式功能簡述**
| 模組名稱           | 功能概要                         |
| ------------------ | -------------------------------- |
| parser.py          | 解析 (meta)、(title)、og: 等資訊 |
| classifier.py      | 判斷連結類型（FB/IG/外部網站     |
| inspect.py         | 檢視HTML結構與除錯               |
| utils.py           | 通用工具與例外處理               |
| test_classifier.py | 測試分類正確性與執行時間         |
| fetcher.py         | 擷取HTM，控制timeout、redirect   |


Ⅳ. **程式之執行方式、使用方式及必要環境設定**
| 需求套件名稱  | 版本   |
| ------------- | ------ |
| pytest        | 8.3.0  |
| beautifulsoup | 4.12.3 |
| request       | 2.31.0 |


> ### 📝 更新紀錄(每日進度回報)
> 
> | 日期 (yyyymmdd) | 更新內容 |
> | --- | --- |
> | 20251018 | {更新github並初始化(Alex)} |
> | 20251019 | {測試 fetch_html 模組與多種 Facebook 連結型態，確認短連結（如 fb.me、l.facebook.com）與正式網址之轉址行為。修正 import 錯誤 (fetcher_html → fetch_html)；新增時間紀錄與 request timeout 控制，確保回傳時間 5 秒。整理截圖測試結果，準備撰寫連結分類邏輯（判斷 FB/IG/外部站）(Alex)。
| 20251020 | {新增 Playwright 模組 (play_fetcher.py) 實現 requests→playwright 自動 fallback；於 inspect.py 加入 fetched_with、duration_ms、was_rewritten、rewritten_url 診斷欄位；成功以 m.facebook.com 抓取多組真實粉專（NASA、UNICEF、WHO、Google、Microsoft）；修正 classifier.py 以辨識 Instagram Reels；測試 fb.watch、group、IG profile/post/reel 共 12 組連結；更新 requirements.txt（新增 playwright），提交 Git 並撰寫 HackMD 詳解章節（Parser × Fallback 流程、日誌、診斷欄位）(Alex)
} |