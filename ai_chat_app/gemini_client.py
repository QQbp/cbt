"""
負責跟 Google Gemini API 溝通的模組。
所有跟 AI 對話 / 分析的請求都會經過這裡的 call_gemini() 函式。
"""
import requests
from flask import current_app

GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
)


class GeminiError(Exception):
    pass


def call_gemini(system_prompt: str, history: list, user_message: str, max_output_tokens: int = 2048) -> str:
    """
    呼叫 Gemini API。

    system_prompt: 這個 AI 的角色設定／訓練指令
    history: [{"role": "user"/"ai", "content": "..."}] 過去的對話紀錄
    user_message: 這一輪使用者輸入的訊息（如果是分析模式，這裡可放整份對話逐字稿）
    max_output_tokens: 回覆內容的長度上限。一般聊天用預設值即可；
        像「生成互動遊戲」這種需要輸出大量結構化內容的功能，呼叫時可以帶入較大的數值，
        避免內容還沒寫完就被截斷。

    回傳 AI 回覆的文字。
    """
    api_key = current_app.config.get("GEMINI_API_KEY")
    model = current_app.config.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

    if not api_key:
        raise GeminiError(
            "尚未設定 GEMINI_API_KEY，請參考安裝說明書，於 .env 檔案中填入你的 Gemini API Key。"
        )

    contents = []
    for m in history:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": max_output_tokens,
            # Gemini 2.5 系列模型預設會啟用「thinking」內部推理，
            # 這個推理過程也會計入 maxOutputTokens，若不關閉，容易導致
            # 實際可見的回覆內容還沒寫完就被截斷。這裡關閉它，讓整個長度
            # 上限都用在真正要輸出的內容上（對聊天陪伴/生成結構化內容的
            # 使用情境來說不需要額外的推理步驟）。
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    url = GEMINI_URL_TEMPLATE.format(model=model, api_key=api_key)

    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = resp.text  # noqa
        except Exception:
            pass
        raise GeminiError(f"呼叫 Gemini API 失敗：{e} {detail}")

    data = resp.json()

    try:
        candidate = data["candidates"][0]
        parts = candidate["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise KeyError("empty text")
        return text
    except (KeyError, IndexError):
        # 有可能被安全機制擋下，或是回傳格式不同
        finish_reason = data.get("candidates", [{}])[0].get("finishReason", "未知")
        raise GeminiError(f"Gemini 沒有回傳有效內容（finishReason: {finish_reason}）。原始回應：{data}")


def generate_image_base64(prompt: str) -> str:
    """
    呼叫 Gemini 的圖像生成模型（Nano Banana），把文字描述畫成一張圖片。

    回傳值是可以直接放進 <img src="..."> 的 data URI 字串，
    例如 "data:image/png;base64,iVBORw0KGgo..."。

    注意：這個功能會產生額外的 Gemini API 費用（依圖片張數計費）。
    """
    api_key = current_app.config.get("GEMINI_API_KEY")
    model = current_app.config.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

    if not api_key:
        raise GeminiError("尚未設定 GEMINI_API_KEY，請參考安裝說明書於 .env 檔案中填入你的 Gemini API Key。")

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    url = GEMINI_URL_TEMPLATE.format(model=model, api_key=api_key)

    try:
        resp = requests.post(url, json=payload, timeout=90)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = resp.text  # noqa
        except Exception:
            pass
        raise GeminiError(f"呼叫 Gemini 圖像生成失敗：{e} {detail}")

    data = resp.json()

    try:
        parts = data["candidates"][0]["content"]["parts"]
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                return f"data:{mime_type};base64,{inline['data']}"
        raise KeyError("回應中沒有圖片資料")
    except (KeyError, IndexError):
        finish_reason = data.get("candidates", [{}])[0].get("finishReason", "未知")
        raise GeminiError(f"Gemini 沒有回傳圖片內容（finishReason: {finish_reason}）。原始回應：{data}")
