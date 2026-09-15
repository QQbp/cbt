"""
負責跟 Unsplash 圖片搜尋 API 溝通的模組。
用於「生成互動遊戲」功能中，選擇「AI 自動搜尋網路圖片」時，
依照每個劇情節點的關鍵字，搜尋一張免費授權、可商用的照片。

Unsplash 官方要求使用其 API 時，畫面上要附上「Photo by 攝影師 on Unsplash」的出處標示，
並附上連結，這裡回傳的 credit_text / credit_url 就是給前端顯示這個標示用的，
使用這個功能時請不要把這個標示拿掉。
"""
import requests

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"


class ImageSearchError(Exception):
    pass


def search_stock_image(query: str, access_key: str):
    """
    依關鍵字搜尋一張圖片。

    query: 搜尋關鍵字（建議用英文，搜尋結果比較準確）
    access_key: Unsplash 的 Access Key

    回傳：
        - 找到圖片時，回傳 dict：
          {"url": 圖片網址, "credit_text": "Photo by 攝影師姓名 on Unsplash", "credit_url": 攝影師頁面網址}
        - 沒有搜尋結果時，回傳 None
    """
    if not access_key:
        raise ImageSearchError(
            "尚未設定 UNSPLASH_ACCESS_KEY，請參考安裝說明書，於 .env 檔案中填入你的 Unsplash Access Key。"
        )

    headers = {"Authorization": f"Client-ID {access_key}"}
    params = {"query": query, "per_page": 1, "orientation": "landscape"}

    try:
        resp = requests.get(UNSPLASH_SEARCH_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = resp.text  # noqa
        except Exception:
            pass
        raise ImageSearchError(f"呼叫 Unsplash 圖片搜尋失敗：{e} {detail}")

    data = resp.json()
    results = data.get("results") or []
    if not results:
        return None

    photo = results[0]
    user = photo.get("user", {}) or {}
    photographer_name = user.get("name", "Unsplash 攝影師")
    photographer_url = (user.get("links", {}) or {}).get("html", "https://unsplash.com")

    return {
        "url": photo.get("urls", {}).get("regular"),
        "credit_text": f"Photo by {photographer_name} on Unsplash",
        "credit_url": photographer_url,
    }
