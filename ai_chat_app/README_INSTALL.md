# 安裝說明書

本專案是一個以 **Python (Flask)** 打造的 AI 對話陪伴網站，內建五個 AI（日記模式、主題模式、分析模式、故事模式、遊戲模式），並串接 **Google Gemini API**（含文字對話與圖像生成）。

## 專案結構

```
ai_chat_app/
├── app.py                # 主程式（所有網頁路由）
├── config.py              # 設定檔（讀取 .env）
├── extensions.py          # Flask 擴充套件初始化
├── models.py               # 資料庫模型（帳號、對話紀錄、AI 指令、參考資料庫）
├── gemini_client.py        # 串接 Gemini API 的程式
├── requirements.txt        # 所需的 Python 套件清單
├── .env.example             # 環境變數範例檔（請複製成 .env）
├── instance/                # 資料庫檔案會自動產生在這裡（SQLite）
├── static/
│   ├── style.css
│   └── chat.js
└── templates/               # 網頁畫面（HTML）
```

## 第一步：確認環境

1. 安裝 **Python 3.10 以上版本**（前往 https://www.python.org/downloads/ 下載）
2. 打開終端機 / 命令提示字元，確認安裝成功：
   ```bash
   python3 --version
   ```

## 第二步：下載專案並建立虛擬環境

```bash
cd ai_chat_app

# 建立虛擬環境（避免跟電腦上其他 Python 專案的套件互相干擾）
python3 -m venv venv

# 啟用虛擬環境
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate
```

## 第三步：安裝所需套件

```bash
pip install -r requirements.txt
```

## 第四步：設定環境變數（.env）

1. 複製一份 `.env.example`，改名為 `.env`：
   ```bash
   cp .env.example .env
   ```
2. 打開 `.env`，需要填入以下兩項最重要的資訊：

   ### 4-1. SECRET_KEY
   這是 Flask 用來加密登入狀態(session)的金鑰，隨便打一串英數字即可，或用下面指令產生：
   ```bash
   python3 -c "import secrets;print(secrets.token_hex(16))"
   ```
   把產生的字串貼到 `.env` 的 `SECRET_KEY=` 後面。

   ### 4-2. GEMINI_API_KEY（**這是最重要的一步，用來串接 Gemini AI**）
   取得方式：
   1. 前往 Google AI Studio：**https://aistudio.google.com/apikey**
   2. 使用你的 Google 帳號登入
   3. 點選畫面上的「**Create API key**」（建立 API 金鑰）按鈕
   4. 複製產生的金鑰字串
   5. 打開專案裡的 `.env` 檔案，貼到這一行的後面：
      ```
      GEMINI_API_KEY=貼在這裡
      ```
   6. 存檔即可，**不需要修改程式碼**。

   > ⚠️ `.env` 檔案內含機密金鑰，請勿上傳到公開的 GitHub 倉庫或分享給不信任的人。

   ### 4-3. GEMINI_MODEL / GEMINI_IMAGE_MODEL（可選）
   - `GEMINI_MODEL` 預設是 `gemini-2.5-flash`，是文字對話用的模型，速度快、成本低，一般情況不需要更動。
   - `GEMINI_IMAGE_MODEL` 預設是 `gemini-2.5-flash-image`，是「生成互動遊戲」功能中，
     選擇「AI 自動繪製插圖」時會用到的圖像生成模型。**這個功能會依生成的圖片張數額外計費**，
     如果使用者在遊戲功能中改選「自己上傳圖片」或「AI 自動搜尋網路圖片」，就完全不會呼叫這個模型、不會有這筆費用。

   ### 4-4. UNSPLASH_ACCESS_KEY（可選，完全免費）
   這組金鑰是「生成互動遊戲」功能中，選擇「AI 自動搜尋網路圖片」這個選項時才會用到，
   如果不打算使用這個選項，可以跳過這一步不填。取得方式：
   1. 前往 **https://unsplash.com/developers** 註冊一個開發者帳號（可以直接用現有帳號登入）
   2. 點選「Your apps」→「New Application」，依畫面指示勾選同意條款、填寫應用程式名稱等資訊
   3. 建立完成後，在應用程式頁面會看到「Access Key」，複製貼到 `.env` 的
      `UNSPLASH_ACCESS_KEY=` 後面
   4. Unsplash 提供免費額度使用，但有請求次數限制，實際額度請以 Unsplash 官方文件為準；
      如果額度用完，使用者選擇這個選項時會看到錯誤訊息，但不影響其他功能正常使用

   ### 4-5. 串接你自己電腦上的本機 AI（Ollama，可選）
   如果你不想每次對話都呼叫 Gemini 雲端 API（例如想省費用、或想離線使用），
   可以把「日記模式 AI」「主題模式 AI」（或其他 AI）改成呼叫你電腦上跑的本機 **Ollama** 模型。
   這一步**不需要修改 `.env`**，是在網站啟動後於「管理後台」裡切換，詳見下方「安裝 Ollama」與
   使用說明書「管理者後台操作說明」章節。

   簡單版設定步驟：
   1. 到 **https://ollama.com** 下載並安裝 Ollama
   2. 開啟終端機，下載一個模型，例如：
      ```bash
      ollama pull llama3.1:8b
      ```
   3. 確認 Ollama 服務有在背景執行（安裝完成後通常會自動啟動；也可以手動執行 `ollama serve`）
   4. 用瀏覽器打開你的網站，登入管理者帳號，進入「管理後台」→「AI 指令設定」，
      在想要串接本機模型的那張 AI 卡片，選擇「💻 本機 Ollama 模型」，
      填入模型名稱（例如 `llama3.1:8b`）與服務網址（本機預設 `http://localhost:11434`），按下更新即可
   5. 之後這個 AI 的對話，就會改成呼叫你電腦上的 Ollama，不會再呼叫 Gemini、不會再產生 Gemini 的費用

   > 提醒：本機模型的能力通常比 Gemini 雲端模型弱，尤其「生成互動遊戲」功能需要 AI 輸出精確的
   > JSON 格式，本機小模型不一定能穩定做到，建議「分析模式」「故事模式」「遊戲模式」這幾個
   > 還是保留用 Gemini，主要把「日記模式」「主題模式」這種一般聊天對話改用本機模型即可。

## 第五步：啟動網站

```bash
python3 app.py
```

啟動成功後，終端機會顯示類似下面的訊息：
```
 * Running on http://0.0.0.0:5000
```

打開瀏覽器輸入：**http://localhost:5000** 即可看到網站。

> 資料庫（帳號、對話紀錄等）會在第一次啟動時，自動建立在 `instance/app.db`（SQLite 檔案），不需要另外安裝資料庫伺服器。

## 第六步：建立第一個帳號（管理者帳號）

1. 進入網站後，點選「註冊」，設定你自己的帳號密碼。
2. **系統設計為：第一個註冊的帳號會自動成為「管理者」**，可以看到「管理後台」選單，
   用來訓練 AI（下指令）以及管理參考資料庫。
3. 之後其他人註冊的帳號，都會是一般使用者（沒有管理後台權限）。

## 常見問題

- **Q: 更新程式碼後（例如新增了故事功能、串接本機 Ollama），需要重新設定資料庫嗎？**
  A: 不需要手動處理。系統啟動時會自動幫既有的資料庫新增缺少的資料表或欄位（例如故事紀錄表、
     AI 供應商設定欄位），原本已經有的帳號、對話紀錄都會完整保留，只要重新啟動 `python app.py` 即可。
     （這個自動升級目前只支援 SQLite，也就是本專案預設的資料庫；如果你已經換成 PostgreSQL / MySQL，
     需要自行執行對應的 `ALTER TABLE` 指令。）

- **Q: 對話時出現「尚未設定 GEMINI_API_KEY」？**
  A: 代表 `.env` 裡的 `GEMINI_API_KEY` 沒有填寫或格式錯誤，請重新確認第四步。

- **Q: 想要部署到正式的伺服器上（不是自己電腦測試）怎麼辦？**
  A: 正式上線建議使用 `gunicorn` 或 `waitress` 等 WSGI Server，並搭配 Nginx 反向代理，
     且務必把 `app.run(debug=True)` 改成 `debug=False`。這部分需要依照你實際的主機環境調整，
     若不熟悉伺服器架設，建議請工程師協助上線。

- **Q: 想把資料庫從 SQLite 換成 MySQL / PostgreSQL？**
  A: 修改 `.env` 裡的 `DATABASE_URL`，例如：
     `DATABASE_URL=postgresql://使用者:密碼@主機位址/資料庫名稱`，
     並額外安裝對應的資料庫驅動套件（如 `psycopg2-binary`）。
