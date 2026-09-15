import os
import json
import re
import base64
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import (
    login_user, logout_user, login_required, current_user, UserMixin
)

from config import Config
from extensions import db, login_manager
from models import (
    User, Conversation, Message, Analysis, Story, Game, AIConfig, KnowledgeBase, KnowledgeChunk,
    AI_DIARY, AI_TOPIC, AI_ANALYSIS, AI_STORY, AI_GAME, AI_TYPE_LABELS,
)
from gemini_client import call_gemini, generate_image_base64, GeminiError
from image_search_client import search_stock_image, ImageSearchError
from ollama_client import call_ollama, OllamaError
from rag_utils import (
    split_into_chunks, embed_text, cosine_similarity,
    embedding_to_json, embedding_from_json, RagError,
)

DEFAULT_PROMPTS = {
    AI_DIARY: (
        "你是一個溫暖、有耐心的日記陪伴者。使用者會用聊天的方式記錄今天發生的事情與心情，"
        "你的任務是傾聽、適度提出開放式問題，幫助使用者把當天的經歷與感受講得更完整，"
        "但不要說教，也不要給沒有被要求的建議。"
    ),
    AI_TOPIC: (
        "你是一個善於引導討論的主題式聊天夥伴。使用者會選定一個主題與你討論，"
        "你的任務是圍繞該主題提出有深度的問題、提供多元觀點，幫助使用者深入思考，"
        "並保持中立、不強加自己的立場。"
    ),
    AI_ANALYSIS: (
        "你是一個對話分析師。你會收到一份使用者與其他 AI 的完整對話逐字稿，"
        "請你分析這段對話中使用者展現出的情緒、關注的重點、可能的需求，"
        "並用清楚、有條理的方式（可用條列）產出分析結果，語氣客觀、專業、避免下診斷式的結論。"
    ),
    AI_STORY: (
        "你是一個擅長說故事的創作者。你會收到一份使用者與其他 AI 的完整對話逐字稿，"
        "請你把這段對話的內容、情緒與重要細節，改寫成一篇有起承轉合、有劇情張力的短篇故事，"
        "可以適度加入場景描寫、譬喻與情感刻畫，讓內容讀起來像一篇文學作品，"
        "但要忠於對話中提到的事實與情緒基調，不要虛構跟原本內容矛盾的情節。"
        "請先給故事下一個簡短有詩意的標題，再開始寫故事本文。"
    ),
    AI_GAME: (
        "你是一個互動小說遊戲的劇情設計師。你會收到一篇故事文本，請把它改編成一個"
        "「有分支選擇、有多種結局」的互動劇情遊戲。\n\n"
        "【輸出格式規定，非常重要，請務必嚴格遵守】\n"
        "只能輸出一個 JSON 物件，不能有任何 JSON 以外的文字、不能用 ```包住，"
        "格式如下：\n"
        '{\n'
        '  "title": "遊戲標題",\n'
        '  "start_node": "n1",\n'
        '  "nodes": {\n'
        '    "n1": {\n'
        '      "text": "這個劇情節點的敘述文字，用繁體中文，約60~100字",\n'
        '      "image_prompt": "給AI畫圖用的英文場景描述，具體描述畫面內容、氛圍、風格",\n'
        '      "image_hint": "用繁體中文寫給「真人使用者」看的建議，'
        '告訴使用者如果想自己上傳照片/圖片，這個節點適合放什麼樣的畫面，例如：'
        '「建議上傳一張夜晚窗邊、氣氛安靜的照片」",\n'
        '      "search_query": "3到6個英文關鍵字，用空格分隔，適合拿去圖庫網站搜尋現成照片，'
        '例如：quiet city street night rain",\n'
        '      "choices": [\n'
        '        {"text": "選項一的文字", "next": "n2"},\n'
        '        {"text": "選項二的文字", "next": "n3"}\n'
        '      ]\n'
        '    },\n'
        '    "n2": {\n'
        '      "text": "結局的敘述文字",\n'
        '      "image_prompt": "英文場景描述",\n'
        '      "image_hint": "繁體中文的圖片建議",\n'
        '      "search_query": "英文關鍵字",\n'
        '      "is_ending": true,\n'
        '      "ending_title": "結局標題，例如：圓滿的和解"\n'
        '    }\n'
        '  }\n'
        '}\n\n'
        "【內容規定】\n"
        "1. 整個遊戲大約規劃 8 到 10 個節點即可，不要太多，避免內容過長被截斷。\n"
        "2. 至少要有 2 個分支選擇點（也就是某個節點有 2-3 個選項會走向不同節點）。\n"
        "3. 至少要有 2 個不同的結局（is_ending 為 true 的節點），結局的走向、氣氛可以不同"
        "（例如有的溫馨、有的略帶遺憾），但都不要偏離原本故事的精神。\n"
        "4. 每個節點都要有 image_prompt（英文，給AI畫圖用）、image_hint（繁體中文，給真人使用者"
        "決定要上傳什麼照片用）、search_query（英文關鍵字，給圖庫網站搜尋現成照片用），"
        "三者描述的畫面內容要一致，風格統一設定為"
        "「2D visual novel illustration, soft colors, warm atmosphere」這種調性，"
        "並加上這個節點特有的場景、人物動作、情緒描述。search_query 要盡量具體、"
        "偏向「實際存在的場景照片」會搜尋到的關鍵字（例如寫實的街景、自然風景、物件），"
        "避免寫太抽象或太像插畫才有的描述。\n"
        "5. 沒有 choices 或 choices 為空陣列的節點，一律視為結局節點，要標記 is_ending: true。"
    ),
}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        db.create_all()
        _ensure_ai_config_columns()
        _ensure_default_ai_configs()

    register_routes(app)
    return app


def _ensure_ai_config_columns():
    """
    簡易資料庫升級：確保 ai_configs 資料表有 provider / ollama_model / ollama_base_url 欄位。

    這是為了讓「已經在使用中、資料庫裡已經有資料」的舊安裝，更新程式碼後不需要手動
    刪除資料庫重建，也能自動補上這幾個新欄位（不需要另外安裝 Flask-Migrate 之類的
    資料庫遷移工具）。目前只處理 SQLite（本專案預設的資料庫）；如果你把 DATABASE_URL
    換成 PostgreSQL / MySQL，這個自動升級不會執行，需要自行執行對應的 ALTER TABLE 指令
    （或直接刪除重建資料表，如果還沒有正式資料的話）。
    """
    if db.engine.url.get_backend_name() != "sqlite":
        return

    with db.engine.connect() as conn:
        existing_cols = {row[1] for row in conn.execute(db.text("PRAGMA table_info(ai_configs)"))}
        if "provider" not in existing_cols:
            conn.execute(db.text("ALTER TABLE ai_configs ADD COLUMN provider VARCHAR(20) DEFAULT 'gemini'"))
        if "ollama_model" not in existing_cols:
            conn.execute(db.text("ALTER TABLE ai_configs ADD COLUMN ollama_model VARCHAR(100) DEFAULT 'llama3.1:8b'"))
        if "ollama_base_url" not in existing_cols:
            conn.execute(db.text(
                "ALTER TABLE ai_configs ADD COLUMN ollama_base_url VARCHAR(200) DEFAULT 'http://localhost:11434'"
            ))
        conn.commit()


def _ensure_default_ai_configs():
    """第一次啟動時，若資料庫還沒有三個 AI 的設定，就寫入預設值"""
    for ai_type, prompt in DEFAULT_PROMPTS.items():
        existing = AIConfig.query.filter_by(ai_type=ai_type).first()
        if not existing:
            db.session.add(AIConfig(ai_type=ai_type, system_prompt=prompt))
    db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def register_routes(app):

    # ---------------- 帳號功能 ----------------

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("chat_home"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")

            if not username or not password:
                flash("帳號與密碼不可空白")
            elif password != confirm:
                flash("兩次輸入的密碼不一致")
            elif User.query.filter_by(username=username).first():
                flash("這個帳號已經被註冊了")
            else:
                is_first_user = User.query.count() == 0
                user = User(username=username, is_admin=is_first_user)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash("註冊成功，請登入" + ("（你是第一個帳號，已自動設為管理者）" if is_first_user else ""))
                return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("welcome_game"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for("welcome_game"))
            flash("帳號或密碼錯誤")

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/welcome")
    @login_required
    def welcome_game():
        """登入後第一個看到的頁面：想法・情緒・行為 小遊戲"""
        return render_template("welcome_game.html")

    # ---------------- 對話功能 ----------------

    @app.route("/")
    @login_required
    def chat_home():
        """選擇模式的首頁"""
        return render_template("chat.html", conversation=None, messages=[])

    @app.route("/chat/start", methods=["POST"])
    @login_required
    def start_conversation():
        mode = request.form.get("mode")
        if mode not in (AI_DIARY, AI_TOPIC):
            flash("請選擇有效的對話模式")
            return redirect(url_for("chat_home"))

        conv = Conversation(user_id=current_user.id, mode=mode)
        db.session.add(conv)
        db.session.commit()
        return redirect(url_for("chat_room", conversation_id=conv.id))

    @app.route("/chat/<int:conversation_id>")
    @login_required
    def chat_room(conversation_id):
        conv = _get_owned_conversation(conversation_id)
        return render_template("chat.html", conversation=conv, messages=conv.messages)

    @app.route("/chat/<int:conversation_id>/send", methods=["POST"])
    @login_required
    def send_message(conversation_id):
        conv = _get_owned_conversation(conversation_id)
        if conv.is_ended:
            return jsonify({"error": "這段對話已結束"}), 400

        user_text = (request.json or {}).get("message", "").strip()
        if not user_text:
            return jsonify({"error": "訊息不可空白"}), 400

        ai_config = AIConfig.query.filter_by(ai_type=conv.mode).first()
        system_prompt = _build_system_prompt(conv.mode, ai_config.system_prompt, query_text=user_text)

        history = [{"role": m.role, "content": m.content} for m in conv.messages]

        user_msg = Message(conversation_id=conv.id, role="user", content=user_text)
        db.session.add(user_msg)
        db.session.commit()

        try:
            ai_reply = _call_ai(ai_config, system_prompt, history, user_text)
        except (GeminiError, OllamaError) as e:
            return jsonify({"error": str(e)}), 500

        ai_msg = Message(conversation_id=conv.id, role="ai", content=ai_reply)
        db.session.add(ai_msg)
        db.session.commit()

        return jsonify({"reply": ai_reply})

    @app.route("/chat/<int:conversation_id>/end", methods=["POST"])
    @login_required
    def end_conversation(conversation_id):
        conv = _get_owned_conversation(conversation_id)
        conv.is_ended = True
        conv.ended_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"status": "ended"})

    @app.route("/chat/<int:conversation_id>/analyze", methods=["POST"])
    @login_required
    def analyze_conversation(conversation_id):
        conv = _get_owned_conversation(conversation_id)

        if not conv.messages:
            return jsonify({"error": "這段對話還沒有任何內容，無法分析"}), 400

        # 把對話整理成 AI 容易閱讀的逐字稿格式
        mode_label = "日記模式" if conv.mode == AI_DIARY else "主題模式"
        lines = [f"【以下是使用者在{mode_label}中的完整對話逐字稿】"]
        for m in conv.messages:
            speaker = "使用者" if m.role == "user" else "AI"
            lines.append(f"{speaker}：{m.content}")
        transcript = "\n".join(lines)

        ai_config = AIConfig.query.filter_by(ai_type=AI_ANALYSIS).first()
        system_prompt = _build_system_prompt(AI_ANALYSIS, ai_config.system_prompt, query_text=transcript)

        try:
            result = _call_ai(ai_config, system_prompt, [], transcript)
        except (GeminiError, OllamaError) as e:
            return jsonify({"error": str(e)}), 500

        analysis = Analysis(conversation_id=conv.id, content=result)
        db.session.add(analysis)
        db.session.commit()

        return jsonify({"analysis": result})

    @app.route("/chat/<int:conversation_id>/story", methods=["POST"])
    @login_required
    def generate_story(conversation_id):
        conv = _get_owned_conversation(conversation_id)

        if not conv.messages:
            return jsonify({"error": "這段對話還沒有任何內容，無法生成故事"}), 400

        mode_label = "日記模式" if conv.mode == AI_DIARY else "主題模式"
        lines = [f"【以下是使用者在{mode_label}中的完整對話逐字稿，請將它改寫成一篇故事】"]
        for m in conv.messages:
            speaker = "使用者" if m.role == "user" else "AI"
            lines.append(f"{speaker}：{m.content}")
        transcript = "\n".join(lines)

        ai_config = AIConfig.query.filter_by(ai_type=AI_STORY).first()
        system_prompt = _build_system_prompt(AI_STORY, ai_config.system_prompt, query_text=transcript)

        try:
            result = _call_ai(ai_config, system_prompt, [], transcript)
        except (GeminiError, OllamaError) as e:
            return jsonify({"error": str(e)}), 500

        story = Story(conversation_id=conv.id, content=result)
        db.session.add(story)
        db.session.commit()

        return jsonify({"story": result})

    @app.route("/chat/<int:conversation_id>/make_game", methods=["POST"])
    @login_required
    def make_game(conversation_id):
        conv = _get_owned_conversation(conversation_id)

        story = (
            Story.query.filter_by(conversation_id=conv.id)
            .order_by(Story.created_at.desc())
            .first()
        )
        if not story:
            return jsonify({"error": "請先按「生成故事」，產生故事之後才能做成互動遊戲"}), 400

        image_mode = (request.json or {}).get("image_mode", "ai")
        if image_mode not in ("ai", "upload", "search"):
            image_mode = "ai"

        ai_config = AIConfig.query.filter_by(ai_type=AI_GAME).first()
        system_prompt = _build_system_prompt(AI_GAME, ai_config.system_prompt, query_text=story.content)

        try:
            raw = _call_ai(ai_config, system_prompt, [], story.content, max_output_tokens=12000)
        except (GeminiError, OllamaError) as e:
            return jsonify({"error": str(e)}), 500

        try:
            game_data = _parse_game_json(raw)
            nodes = game_data["nodes"]
            assert game_data.get("start_node") in nodes
        except Exception as e:
            # 把 AI 實際回傳的原始內容印到終端機，方便管理者排查為什麼解析失敗
            app.logger.error("遊戲 JSON 解析失敗：%s\n----- AI 原始回應開始 -----\n%s\n----- AI 原始回應結束 -----", e, raw)
            return jsonify({"error": "AI 產生的遊戲資料格式有誤，請再試一次（詳細內容已印在後端終端機）"}), 500

        if image_mode == "ai":
            # 自動幫每個節點生成插圖（會產生額外的 Gemini 圖像生成費用）
            for node in nodes.values():
                prompt = node.get("image_prompt")
                if not prompt:
                    continue
                try:
                    node["image_data"] = generate_image_base64(prompt)
                except GeminiError:
                    node["image_data"] = None  # 該節點沒有圖片也沒關係，遊戲仍可進行
        elif image_mode == "search":
            # 依每個節點的關鍵字，去 Unsplash 搜尋現成的免費照片（完全免費，不會有 Gemini 圖像生成費用）
            unsplash_key = app.config.get("UNSPLASH_ACCESS_KEY")
            for node in nodes.values():
                query = node.get("search_query") or node.get("image_prompt")
                if not query:
                    node["image_data"] = None
                    continue
                try:
                    result = search_stock_image(query, unsplash_key)
                except ImageSearchError as e:
                    return jsonify({"error": str(e)}), 500
                if result and result.get("url"):
                    node["image_data"] = result["url"]
                    node["image_credit_text"] = result["credit_text"]
                    node["image_credit_url"] = result["credit_url"]
                else:
                    node["image_data"] = None  # 沒搜尋到合適的圖片也沒關係，遊戲仍可進行
        else:
            # 使用者選擇自行上傳，先不產生圖片，留給使用者在上傳頁面自己補
            for node in nodes.values():
                node["image_data"] = None

        game_data["image_mode"] = image_mode

        game = Game(
            conversation_id=conv.id,
            title=game_data.get("title", "我的互動故事"),
            data_json=json.dumps(game_data, ensure_ascii=False),
        )
        db.session.add(game)
        db.session.commit()

        return jsonify({"game_id": game.id, "image_mode": image_mode})

    @app.route("/game/<int:game_id>")
    @login_required
    def play_game(game_id):
        game = _get_owned_game(game_id)
        return render_template("game.html", game=game)

    @app.route("/game/<int:game_id>/upload")
    @login_required
    def game_upload_page(game_id):
        game = _get_owned_game(game_id)
        game_data = json.loads(game.data_json)
        nodes = game_data.get("nodes", {})
        # 依照 JSON 內的順序（AI 產生時大致上就是劇情發展順序）逐一列出節點
        node_list = [{"id": nid, **ndata} for nid, ndata in nodes.items()]
        return render_template("game_upload.html", game=game, node_list=node_list)

    @app.route("/game/<int:game_id>/upload", methods=["POST"])
    @login_required
    def game_upload_submit(game_id):
        game = _get_owned_game(game_id)
        game_data = json.loads(game.data_json)
        nodes = game_data.get("nodes", {})

        for node_id in nodes.keys():
            file = request.files.get(f"image_{node_id}")
            if file and file.filename:
                mime_type = file.mimetype or "image/png"
                if not mime_type.startswith("image/"):
                    continue  # 忽略不是圖片格式的檔案
                encoded = base64.b64encode(file.read()).decode("ascii")
                nodes[node_id]["image_data"] = f"data:{mime_type};base64,{encoded}"

        game.data_json = json.dumps(game_data, ensure_ascii=False)
        db.session.commit()

        flash("圖片已上傳完成，可以開始遊玩了！")
        return redirect(url_for("play_game", game_id=game.id))

    def _get_owned_game(game_id):
        game = Game.query.get_or_404(game_id)
        if game.conversation.user_id != current_user.id:
            from flask import abort
            abort(403)
        return game

    def _parse_game_json(raw_text):
        """
        把 AI 回傳的文字清乾淨之後解析成 JSON。
        AI 有時候會在 JSON 前後多加說明文字，或用 ```json ... ``` 包住，這裡盡量都容錯處理。
        """
        text = raw_text.strip()
        text = re.sub(r"^```(json)?", "", text.strip())
        text = re.sub(r"```$", "", text.strip())
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 退而求其次：只擷取第一個 { 到最後一個 } 之間的內容，去掉前後可能夾雜的說明文字
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])

        raise ValueError("找不到有效的 JSON 內容")

    def _get_owned_conversation(conversation_id):
        conv = Conversation.query.get_or_404(conversation_id)
        if conv.user_id != current_user.id:
            from flask import abort
            abort(403)
        return conv

    def _rebuild_chunks_for_kb(kb):
        """幫一筆參考資料切段、向量化，存進 KnowledgeChunk（新增資料時呼叫一次即可）"""
        KnowledgeChunk.query.filter_by(knowledge_base_id=kb.id).delete()
        full_text = f"{kb.title}：{kb.content}"
        pieces = split_into_chunks(full_text)
        for piece in pieces:
            vector = embed_text(piece)  # 若 Gemini API 有問題，會在這裡拋出 RagError，交由呼叫端處理
            chunk = KnowledgeChunk(
                knowledge_base_id=kb.id,
                ai_type=kb.ai_type,
                chunk_text=piece,
                embedding_json=embedding_to_json(vector),
            )
            db.session.add(chunk)
        db.session.commit()

    def _retrieve_relevant_chunks(ai_type, query_text, top_k=4, min_score=0.3):
        """依照目前的查詢內容（使用者訊息/對話逐字稿等），從這個 AI 的參考資料庫中找出最相關的幾段"""
        chunks = KnowledgeChunk.query.filter_by(ai_type=ai_type).all()
        if not chunks:
            return []

        query_vector = embed_text(query_text[:2000])  # 查詢文字太長時先截斷，避免超過向量化 API 的長度限制

        scored = []
        for c in chunks:
            try:
                vec = embedding_from_json(c.embedding_json)
            except (ValueError, TypeError):
                continue
            score = cosine_similarity(query_vector, vec)
            scored.append((score, c.chunk_text))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [text for score, text in scored[:top_k] if score >= min_score]

    def _build_system_prompt(ai_type, base_prompt, query_text=None):
        """
        把參考資料庫中最相關的內容，接在 system prompt 後面。

        這是 RAG（檢索增強生成）的做法：只挑跟 query_text 語意最相關的幾段參考資料，
        而不是把整個知識庫全部塞進去，避免資料一多就超過 AI 能接收的長度上限。
        如果向量化服務暫時有問題（例如 Gemini API Key 沒設定好），會靜靜地略過參考資料，
        不影響一般對話功能正常運作。
        """
        if query_text:
            try:
                relevant = _retrieve_relevant_chunks(ai_type, query_text)
            except RagError:
                relevant = []
            if relevant:
                kb_text = "\n\n".join(f"- {c}" for c in relevant)
                return f"{base_prompt}\n\n【以下是根據目前內容，從參考資料庫中找到最相關的段落，請在合適的時候納入考量】\n{kb_text}"
            return base_prompt

        # 沒有查詢內容可用時的保險路徑：退回舊版「全部塞進去」的方式
        kb_items = KnowledgeBase.query.filter_by(ai_type=ai_type).all()
        if not kb_items:
            return base_prompt
        kb_text = "\n\n".join(f"- {kb.title}：{kb.content}" for kb in kb_items)
        return f"{base_prompt}\n\n【以下是管理者提供的參考資料，請在合適的時候納入考量】\n{kb_text}"

    def _call_ai(ai_config, system_prompt, history, user_message, max_output_tokens=2048):
        """
        依照這個 AI 目前設定的供應商，呼叫 Gemini 或是本機 Ollama 模型。
        兩種情況都可能拋出例外（GeminiError 或 OllamaError），呼叫端請一併攔截這兩種。
        """
        if ai_config.provider == "ollama":
            return call_ollama(
                system_prompt,
                history,
                user_message,
                model=ai_config.ollama_model or "llama3.1:8b",
                base_url=ai_config.ollama_base_url or "http://localhost:11434",
                max_output_tokens=max_output_tokens,
            )
        return call_gemini(system_prompt, history, user_message, max_output_tokens=max_output_tokens)

    # ---------------- 管理者後台 ----------------

    def _admin_required():
        if not current_user.is_authenticated or not current_user.is_admin:
            from flask import abort
            abort(403)

    @app.route("/admin")
    @login_required
    def admin_home():
        _admin_required()
        return redirect(url_for("admin_ai_list"))

    @app.route("/admin/ai")
    @login_required
    def admin_ai_list():
        _admin_required()
        configs = {c.ai_type: c for c in AIConfig.query.all()}
        return render_template(
            "admin_ai.html", configs=configs, labels=AI_TYPE_LABELS,
            order=[AI_DIARY, AI_TOPIC, AI_ANALYSIS, AI_STORY, AI_GAME],
        )

    @app.route("/admin/ai/<ai_type>", methods=["POST"])
    @login_required
    def admin_ai_update(ai_type):
        _admin_required()
        if ai_type not in AI_TYPE_LABELS:
            flash("無效的 AI 類型")
            return redirect(url_for("admin_ai_list"))

        new_prompt = request.form.get("system_prompt", "").strip()
        if not new_prompt:
            flash("指令內容不可空白")
            return redirect(url_for("admin_ai_list"))

        provider = request.form.get("provider", "gemini")
        if provider not in ("gemini", "ollama"):
            provider = "gemini"
        ollama_model = request.form.get("ollama_model", "").strip() or "llama3.1:8b"
        ollama_base_url = request.form.get("ollama_base_url", "").strip() or "http://localhost:11434"

        config = AIConfig.query.filter_by(ai_type=ai_type).first()
        config.system_prompt = new_prompt
        config.provider = provider
        config.ollama_model = ollama_model
        config.ollama_base_url = ollama_base_url
        config.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f"已更新「{AI_TYPE_LABELS[ai_type]}」的訓練指令與供應商設定")
        return redirect(url_for("admin_ai_list"))

    @app.route("/admin/knowledge")
    @login_required
    def admin_knowledge_list():
        _admin_required()
        items = KnowledgeBase.query.order_by(KnowledgeBase.created_at.desc()).all()
        chunk_counts = {
            item.id: KnowledgeChunk.query.filter_by(knowledge_base_id=item.id).count()
            for item in items
        }
        return render_template(
            "admin_knowledge.html", items=items, labels=AI_TYPE_LABELS,
            order=[AI_DIARY, AI_TOPIC, AI_ANALYSIS, AI_STORY, AI_GAME],
            chunk_counts=chunk_counts,
        )

    @app.route("/admin/knowledge/add", methods=["POST"])
    @login_required
    def admin_knowledge_add():
        _admin_required()
        ai_type = request.form.get("ai_type")
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if ai_type not in AI_TYPE_LABELS or not title or not content:
            flash("請完整填寫參考資料的內容")
            return redirect(url_for("admin_knowledge_list"))

        kb = KnowledgeBase(ai_type=ai_type, title=title, content=content)
        db.session.add(kb)
        db.session.commit()

        try:
            _rebuild_chunks_for_kb(kb)
            flash("已新增參考資料，並完成向量化，AI 現在可以用語意搜尋找到這筆資料")
        except RagError as e:
            flash(f"已新增參考資料，但向量化失敗（{e}），AI 暫時可能找不到這筆資料，"
                  f"可以到列表按「重新向量化」再試一次")

        return redirect(url_for("admin_knowledge_list"))

    @app.route("/admin/knowledge/<int:item_id>/reembed", methods=["POST"])
    @login_required
    def admin_knowledge_reembed(item_id):
        _admin_required()
        kb = KnowledgeBase.query.get_or_404(item_id)
        try:
            _rebuild_chunks_for_kb(kb)
            flash("已重新向量化完成")
        except RagError as e:
            flash(f"向量化失敗：{e}")
        return redirect(url_for("admin_knowledge_list"))

    @app.route("/admin/knowledge/<int:item_id>/delete", methods=["POST"])
    @login_required
    def admin_knowledge_delete(item_id):
        _admin_required()
        kb = KnowledgeBase.query.get_or_404(item_id)
        db.session.delete(kb)
        db.session.commit()
        flash("已刪除參考資料")
        return redirect(url_for("admin_knowledge_list"))

    @app.route("/history")
    @login_required
    def history():
        convs = (
            Conversation.query.filter_by(user_id=current_user.id)
            .order_by(Conversation.started_at.desc())
            .all()
        )
        return render_template("history.html", conversations=convs, labels=AI_TYPE_LABELS)


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
