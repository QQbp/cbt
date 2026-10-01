"""
負責跟 Azure AI（Azure OpenAI 相容介面）溝通的模組。

用於「日記模式 AI」「主題模式 AI」等，管理者在後台把該 AI 的供應商切換成
「Azure AI」時，就會經由這裡呼叫，而不是呼叫 Gemini 或本機 Ollama。

前提：在 .env（本機）或 App Service 的環境變數（線上）填好
AZURE_AI_ENDPOINT 與 AZURE_AI_KEY，並且該資源底下已經部署了
AZURE_AI_CHAT_DEPLOYMENT / AZURE_AI_EMBEDDING_DEPLOYMENT 這兩個模型。
"""
import requests
from flask import current_app


class AzureAIError(Exception):
    pass


def _config():
    """讀出連線設定，缺少必要項目時給出明確的錯誤訊息"""
    endpoint = (current_app.config.get("AZURE_AI_ENDPOINT") or "").rstrip("/")
    api_key = current_app.config.get("AZURE_AI_KEY")

    if not endpoint or not api_key:
        raise AzureAIError(
            "尚未設定 Azure AI 連線資訊，請在 .env（本機）或 App Service 的環境變數（線上）"
            "填入 AZURE_AI_ENDPOINT 與 AZURE_AI_KEY。"
        )

    return endpoint, api_key, current_app.config.get("AZURE_AI_API_VERSION", "2024-10-21")


def _post(path: str, payload: dict, timeout: int, what: str) -> dict:
    endpoint, api_key, api_version = _config()
    url = f"{endpoint}/openai/deployments/{path}?api-version={api_version}"

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")  # noqa
        except Exception:
            pass
        raise AzureAIError(f"{what}失敗：{e} {detail}")

    return resp.json()


def call_azure_ai(system_prompt: str, history: list, user_message: str, max_output_tokens: int = 2048) -> str:
    """
    呼叫 Azure AI 的對話介面。參數與回傳值跟 call_gemini / call_ollama 一致，
    方便在後台切換供應商時共用同一段呼叫程式碼。

    注意：gpt-5 系列模型只接受 max_completion_tokens（不是 max_tokens），
    而且 temperature 只能用預設值，所以這裡都不帶 temperature。
    """
    deployment = current_app.config.get("AZURE_AI_CHAT_DEPLOYMENT", "gpt-5-mini")

    messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "messages": messages,
        "max_completion_tokens": max_output_tokens,
        # gpt-5 系列會先做內部推理，推理用掉的 token 也算在 max_completion_tokens 裡，
        # 實測用 low 時推理就可能把額度吃光、回傳空內容。這裡設成 minimal，
        # 推理 token 為 0，額度全部留給真正要輸出的內容，回應也比較快。
        # 聊天陪伴和生成故事這類用途不需要額外的推理步驟。
        "reasoning_effort": "minimal",
    }

    data = _post(f"{deployment}/chat/completions", payload, 180, "呼叫 Azure AI")

    try:
        content = data["choices"][0]["message"]["content"]
        if not content:
            raise KeyError("empty content")
        return content
    except (KeyError, IndexError, TypeError):
        finish_reason = (data.get("choices") or [{}])[0].get("finish_reason", "未知")
        raise AzureAIError(
            f"Azure AI 沒有回傳有效內容（finish_reason: {finish_reason}）。"
            "若是 length，代表長度上限用完了，可以調高 max_output_tokens。"
        )


def embed_text(text: str) -> list:
    """呼叫 Azure AI 的向量化模型，把一段文字轉成向量（一組浮點數列表）"""
    deployment = current_app.config.get("AZURE_AI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

    data = _post(f"{deployment}/embeddings", {"input": text}, 60, "呼叫 Azure AI 向量化")

    try:
        values = data["data"][0]["embedding"]
        if not values:
            raise KeyError("empty values")
        return values
    except (KeyError, IndexError, TypeError):
        raise AzureAIError(f"Azure AI 沒有回傳有效的向量資料。原始回應：{data}")
