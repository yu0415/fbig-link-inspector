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
**內容撰寫指引**
1. 確實記錄所有**相關重要成果**  
2. 此內容將隨討論持續更新  
3. **GitHub 相關連結**需完整記錄  
4. 內容架構包含：
Ⅰ. **工作日期 / 工作目標（進度或欲解決之問題） / 行業別 / 作業過程與方法** 
工作日期：2025/10/19
工作目標：
開發一個能在輸入任意 Facebook 或 Instagram 連結後，自動辨識「連結類型」與「基礎資訊」的模組。
核心要求：
1️⃣ 能辨識多種連結型態（短連結、分享連結、外部嵌入連結、用戶頁面）
2️⃣ 回傳結果需於 5 秒內完成
3️⃣ 程式結構模組化、易於擴充與前端 API 整合
	•	行業別：社群媒體資料分析 / 網路爬蟲自動化
    過程方法敘述 
    （一）過程方法敘述
	1.	建立專案結構（src/, tests/, requirements.txt, README.md）。
	2.	完成 fetcher.py 用於安全擷取 URL HTML，含 timeout 與 redirect 控制。
	3.	設計 parser.py 與 inspect.py 處理 meta fallback（支援meta[name<title>,og:image）。
	4.	建立 classifier.py，用於後續連結型態分類（FB / IG / 外部）。
	5.	建立 tests/test_classifier.py 用於基礎自動化測試。
	6.	驗證多組連結（fb.me, l.facebook.com, facebook.com/share,instagram.com/reel/...）。
   - 使用之程式方法  
   - 使用之工具  
   - **完成事項**（進度或解決之問題）  
   - **工作檔案連結**（包括程式原始碼、完成事項之工作檔案，如使用 excel 記錄資料庫設計格式）  
   - 未解決之問題  
   - 工作計畫

Ⅱ. **程式檔案名稱與存放路徑**
fbig-link-inspector/
├----─ src/
│xxxxxx├── __init__.py
│xxxxxx├── classifier.py 
│xxxxxx├── fetcher.py
│xxxxxx├── inspect.py
│xxxxxx├── parser.py
│xxxxxx└── utils.py
│
├── tests/
│xxxxxx├── __init__.py
│xxxxxx└── test_classifier.py  # 自動化測試 - 連結分類與速度驗證
│
├── .gitignore
├── README.md
└── requirements.txt

Ⅲ. **程式功能簡述**

Ⅳ. **程式之執行方式、使用方式及必要環境設定**

Ⅴ. **記載內容應足以支援任務成果之後續應用或後續調整增刪**

Ⅵ. **其他甲方要求之規範**
＿＿＿
> ### 📝 更新紀錄(每日進度回報)
> 
> | 日期 (yyyymmdd) | 更新內容 |
> | --- | --- |
> | 20251018 | {更新github並初始化(Alex)} |
> | 20251019 | {測試 fetch_html 模組與多種 Facebook 連結型態，確認短連結（如 fb.me、l.facebook.com）與正式網址之轉址行為。修正 import 錯誤 (fetcher_html → fetch_html)；新增時間紀錄與 request timeout 控制，確保回傳時間 <5 秒。整理截圖測試結果，準備撰寫連結分類邏輯（判斷 FB/IG/外部站）(Alex)。
} |
> [color=#F9CD88]