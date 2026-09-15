"""
負責跟本機（或區網內）Ollama 服務溝通的模組。
用於「日記模式 AI」「主題模式 AI」等，管理者在後台把該 AI 的供應商切換成
「本機 Ollama 模型」時，就會經由這裡呼叫，而不是呼叫 Gemini。

前提：你的電腦（或伺服器）上已經安裝並啟動 Ollama（例如執行過 `ollama serve`，
或安裝了 Ollama Desktop 讓它保持在背景執行），且已經用 `ollama pull llama3.1:8b`
之類的指令下載過對應的模型。
"""
import requests


class OllamaError(Exception):
    pass


def call_ollama(
    system_prompt: str,
    history: list,
    user_message: str,
    model: str = "llama3.1:8b",
    base_url: str = "http://localhost:11434",
    max_output_tokens: int = 2048,
) -> str:
    """
    呼叫本機 Ollama 的 /api/chat 介面。

    system_prompt: 這個 AI 的角色設定／訓練指令
    history: [{"role": "user"/"ai", "content": "..."}] 過去的對話紀錄
    user_message: 這一輪使用者輸入的訊息
    model: Ollama 裡已經下載好的模型名稱，例如 "llama3.1:8b"
    base_url: Ollama 服務的網址，本機預設是 http://localhost:11434；
        如果 Ollama 是跑在區網內另一台電腦上，改成那台電腦的網址即可
    max_output_tokens: 回覆內容的長度上限（對應 Ollama 的 num_predict 參數）

    回傳 AI 回覆的文字。
    """
    messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": max_output_tokens,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=180)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise OllamaError(
            f"無法連線到本機 Ollama 服務（{base_url}）。"
            "請確認電腦上的 Ollama 有啟動（可以先在終端機執行 `ollama serve`，"
            "或打開 Ollama Desktop 應用程式），並確認網址與連接埠設定正確。"
        )
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = resp.text  # noqa
        except Exception:
            pass
        raise OllamaError(f"呼叫本機 Ollama 模型失敗：{e} {detail}")

    data = resp.json()

    try:
        content = data["message"]["content"]
        if not content:
            raise KeyError("empty content")
        return content
    except (KeyError, TypeError):
        raise OllamaError(
            f"Ollama 沒有回傳有效內容，請確認模型名稱「{model}」是否已經用 "
            f"`ollama pull {model}` 下載過。原始回應：{data}"
        )
