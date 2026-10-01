import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-請務必更改")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Azure AI（Azure OpenAI 相容介面）。端點長得像
    # https://你的資源名稱.cognitiveservices.azure.com/
    # 部署名稱是你在 Azure 上替模型取的名字，不一定等於模型本身的名稱。
    AZURE_AI_ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT", "")
    AZURE_AI_KEY = os.environ.get("AZURE_AI_KEY", "")
    AZURE_AI_CHAT_DEPLOYMENT = os.environ.get("AZURE_AI_CHAT_DEPLOYMENT", "gpt-5-mini")
    AZURE_AI_EMBEDDING_DEPLOYMENT = os.environ.get(
        "AZURE_AI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
    )
    AZURE_AI_API_VERSION = os.environ.get("AZURE_AI_API_VERSION", "2024-10-21")

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

    # 用於「生成互動遊戲」功能中「AI 自動搜尋網路圖片」選項，非必填
    # 只有使用者選擇這個選項時才會用到，沒設定的話這個選項會顯示錯誤訊息，但不影響其他功能
    UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
