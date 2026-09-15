from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

# AI 種類代碼，整個系統統一使用這幾個字串來代表不同的 AI
AI_DIARY = "diary"      # 日記模式 AI
AI_TOPIC = "topic"      # 主題模式 AI
AI_ANALYSIS = "analysis"  # 分析模式 AI
AI_STORY = "story"      # 故事模式 AI（把對話改寫成有劇情的故事）
AI_GAME = "game"        # 遊戲模式 AI（把故事拆解成互動選擇遊戲的劇情分支）

AI_TYPE_LABELS = {
    AI_DIARY: "日記模式 AI",
    AI_TOPIC: "主題模式 AI",
    AI_ANALYSIS: "分析模式 AI",
    AI_STORY: "故事模式 AI",
    AI_GAME: "遊戲模式 AI",
}


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conversations = db.relationship("Conversation", backref="user", lazy=True)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class Conversation(db.Model):
    """一次對話的紀錄（一個 session），mode 決定當時是跟哪個 AI 對話"""
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mode = db.Column(db.String(20), nullable=False)  # AI_DIARY 或 AI_TOPIC
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    is_ended = db.Column(db.Boolean, default=False)

    messages = db.relationship(
        "Message", backref="conversation", lazy=True,
        order_by="Message.created_at", cascade="all, delete-orphan"
    )
    analyses = db.relationship(
        "Analysis", backref="conversation", lazy=True,
        cascade="all, delete-orphan"
    )
    stories = db.relationship(
        "Story", backref="conversation", lazy=True,
        cascade="all, delete-orphan"
    )
    games = db.relationship(
        "Game", backref="conversation", lazy=True,
        cascade="all, delete-orphan"
    )


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # "user" 或 "ai"
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Analysis(db.Model):
    """分析模式 AI 針對某次對話產出的分析結果"""
    __tablename__ = "analyses"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Story(db.Model):
    """故事模式 AI 把某次對話改寫成的有劇情故事"""
    __tablename__ = "stories"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    title = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Game(db.Model):
    """遊戲模式 AI 把故事拆解成的互動選擇遊戲資料（劇情分支 + 每個節點的插圖，皆存成 JSON）"""
    __tablename__ = "games"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    title = db.Column(db.String(200), nullable=True)
    data_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AIConfig(db.Model):
    """每個 AI 各自的「訓練指令」(system prompt) 與供應商設定，由管理者在後台編輯"""
    __tablename__ = "ai_configs"

    id = db.Column(db.Integer, primary_key=True)
    ai_type = db.Column(db.String(20), unique=True, nullable=False)  # diary/topic/analysis/story/game
    system_prompt = db.Column(db.Text, nullable=False)

    # AI 供應商設定：
    #   provider = "gemini"（預設，走 Google Gemini 雲端 API）
    #            或 "ollama"（走使用者自己電腦上的本機 Ollama 模型）
    provider = db.Column(db.String(20), nullable=False, default="gemini")
    ollama_model = db.Column(db.String(100), nullable=True, default="llama3.1:8b")
    ollama_base_url = db.Column(db.String(200), nullable=True, default="http://localhost:11434")

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeBase(db.Model):
    """管理者存放的參考資料，會依照 ai_type 提供給對應的 AI 當作額外參考資訊"""
    __tablename__ = "knowledge_base"

    id = db.Column(db.Integer, primary_key=True)
    ai_type = db.Column(db.String(20), nullable=False)  # 這筆資料要給哪個 AI 參考
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chunks = db.relationship(
        "KnowledgeChunk", backref="knowledge_base", lazy=True,
        cascade="all, delete-orphan"
    )


class KnowledgeChunk(db.Model):
    """
    RAG 用的知識庫分段與向量。

    每一筆 KnowledgeBase 資料在新增時，會被自動切成一或多個小段落(chunk)，
    每一段各自呼叫 Gemini 的向量化 API 算出一組向量(embedding)存起來。
    AI 對話時，會把使用者當下的訊息也轉成向量，跟這裡存的向量比對「語意相似度」，
    只挑最相關的幾段放進 AI 的參考資料，而不是把整個知識庫全部塞進去，
    這樣資料量再多也不容易超過 AI 能接收的長度上限。
    """
    __tablename__ = "knowledge_chunks"

    id = db.Column(db.Integer, primary_key=True)
    knowledge_base_id = db.Column(db.Integer, db.ForeignKey("knowledge_base.id"), nullable=False)
    ai_type = db.Column(db.String(20), nullable=False)  # 冗餘存一份，查詢時可以直接篩選，不用多做一次關聯查詢
    chunk_text = db.Column(db.Text, nullable=False)
    embedding_json = db.Column(db.Text, nullable=False)  # 向量內容，存成 JSON 字串（一串浮點數）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
