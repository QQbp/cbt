"""
簡易的 RAG（Retrieval-Augmented Generation，檢索增強生成）工具模組。

負責三件事：
1. 把管理者存進參考資料庫的長篇內容，切成一小段一小段（chunk）
2. 呼叫 Gemini 的向量化(embedding) API，把每一段文字轉成一組數字向量
3. 對話當下，把使用者的訊息也轉成向量，用「餘弦相似度」比對哪幾段參考資料最相關，
   只把最相關的幾段放進 AI 的系統指令，而不是把整個知識庫全部塞進去
   （避免內容太多超過 AI 能接收的長度上限，尤其是本機 Ollama 模型的上下文通常比較小）

注意：向量化目前固定使用 Google Gemini 的 embedding API（gemini-embedding-001），
不管你把某個 AI 的「對話」供應商設定成 Gemini 還是本機 Ollama，向量化這一步都還是會
呼叫 Gemini，所以需要在 .env 設定好 GEMINI_API_KEY 才能使用這個功能。
"""
import json
import math
import requests
from flask import current_app

EMBEDDING_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={api_key}"
)
EMBEDDING_MODEL = "gemini-embedding-001"

CHUNK_SIZE = 500      # 每一段大約幾個字（含中英文字元）
CHUNK_OVERLAP = 80    # 段落之間重疊幾個字，避免語意被硬生生從中間切斷


class RagError(Exception):
    pass


def split_into_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """把長文字切成多個有重疊的段落；字數不多的話就只會回傳一段"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def embed_text(text: str) -> list:
    """呼叫 Gemini 的向量化 API，把一段文字轉成向量（一組浮點數列表）"""
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        raise RagError(
            "尚未設定 GEMINI_API_KEY，RAG 參考資料庫的向量化功能需要 Gemini API Key 才能使用，"
            "請參考安裝說明書於 .env 檔案中填入你的 Gemini API Key。"
        )

    url = EMBEDDING_URL_TEMPLATE.format(model=EMBEDDING_MODEL, api_key=api_key)
    payload = {"content": {"parts": [{"text": text}]}}

    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = resp.text  # noqa
        except Exception:
            pass
        raise RagError(f"呼叫 Gemini 向量化 API 失敗：{e} {detail}")

    data = resp.json()
    try:
        values = data["embedding"]["values"]
        if not values:
            raise KeyError("empty values")
        return values
    except (KeyError, TypeError):
        raise RagError(f"Gemini 沒有回傳有效的向量資料。原始回應：{data}")


def cosine_similarity(vec_a, vec_b):
    """計算兩組向量的餘弦相似度，值介於 -1 ~ 1，越接近 1 代表語意越相近"""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return -1.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return -1.0
    return dot / (norm_a * norm_b)


def embedding_to_json(vector):
    return json.dumps(vector)


def embedding_from_json(text):
    return json.loads(text)
