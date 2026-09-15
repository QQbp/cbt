(function () {
    const wrapper = document.querySelector(".chat-wrapper");
    if (!wrapper) return;

    const conversationId = wrapper.dataset.conversationId;
    const chatBox = document.getElementById("chat-box");
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const btnEnd = document.getElementById("btn-end");
    const btnAnalyze = document.getElementById("btn-analyze");
    const analysisBox = document.getElementById("analysis-box");
    const btnStory = document.getElementById("btn-story");
    const storyBox = document.getElementById("story-box");
    const btnGame = document.getElementById("btn-game");
    const gameStatus = document.getElementById("game-status");
    const btnMic = document.getElementById("btn-mic");
    const voiceStatus = document.getElementById("voice-status");
    const toggleAiVoice = document.getElementById("toggle-ai-voice");

    function scrollToBottom() {
        chatBox.scrollTop = chatBox.scrollHeight;
    }
    scrollToBottom();

    function addBubble(role, content) {
        const div = document.createElement("div");
        div.className = "bubble " + (role === "user" ? "user" : "ai");
        div.innerHTML = `<div class="bubble-role">${role === "user" ? "你" : "AI"}</div><div class="bubble-content"></div>`;
        div.querySelector(".bubble-content").textContent = content;
        chatBox.appendChild(div);
        scrollToBottom();
    }

    if (chatForm) {
        chatForm.addEventListener("submit", async function (e) {
            e.preventDefault();
            const text = chatInput.value.trim();
            if (!text) return;

            addBubble("user", text);
            chatInput.value = "";
            chatInput.disabled = true;

            try {
                const resp = await fetch(`/chat/${conversationId}/send`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: text }),
                });
                const data = await resp.json();
                if (resp.ok) {
                    addBubble("ai", data.reply);
                    speakText(data.reply);
                } else {
                    addBubble("ai", "⚠️ " + (data.error || "發生錯誤"));
                }
            } catch (err) {
                addBubble("ai", "⚠️ 連線發生錯誤，請稍後再試");
            } finally {
                chatInput.disabled = false;
                chatInput.focus();
            }
        });
    }

    if (btnEnd) {
        btnEnd.addEventListener("click", async function () {
            if (!confirm("確定要結束這段對話嗎？結束後將無法再繼續輸入。")) return;
            const resp = await fetch(`/chat/${conversationId}/end`, { method: "POST" });
            if (resp.ok) {
                chatInput.disabled = true;
                chatForm.querySelector("button").disabled = true;
                btnEnd.disabled = true;
            }
        });
    }

    if (btnAnalyze) {
        btnAnalyze.addEventListener("click", async function () {
            btnAnalyze.disabled = true;
            btnAnalyze.textContent = "分析中...";
            analysisBox.style.display = "block";
            analysisBox.textContent = "AI 正在閱讀這段對話，請稍候...";

            try {
                const resp = await fetch(`/chat/${conversationId}/analyze`, { method: "POST" });
                const data = await resp.json();
                if (resp.ok) {
                    analysisBox.textContent = "📊 分析結果：\n\n" + data.analysis;
                } else {
                    analysisBox.textContent = "⚠️ " + (data.error || "分析失敗");
                }
            } catch (err) {
                analysisBox.textContent = "⚠️ 連線發生錯誤，請稍後再試";
            } finally {
                btnAnalyze.disabled = false;
                btnAnalyze.textContent = "📊 分析這段對話";
            }
        });
    }

    if (btnStory) {
        btnStory.addEventListener("click", async function () {
            btnStory.disabled = true;
            btnStory.textContent = "故事生成中...";
            storyBox.style.display = "block";
            storyBox.textContent = "AI 正在把這段對話改寫成故事，請稍候...";

            try {
                const resp = await fetch(`/chat/${conversationId}/story`, { method: "POST" });
                const data = await resp.json();
                if (resp.ok) {
                    storyBox.textContent = "📖 你的故事：\n\n" + data.story;
                } else {
                    storyBox.textContent = "⚠️ " + (data.error || "生成故事失敗");
                }
            } catch (err) {
                storyBox.textContent = "⚠️ 連線發生錯誤，請稍後再試";
            } finally {
                btnStory.disabled = false;
                btnStory.textContent = "📖 生成故事";
            }
        });
    }
    if (btnGame) {
        btnGame.addEventListener("click", async function () {
            const selectedMode = document.querySelector('input[name="image_mode"]:checked');
            const imageMode = selectedMode ? selectedMode.value : "ai";

            btnGame.disabled = true;
            gameStatus.style.display = "block";
            if (imageMode === "ai") {
                gameStatus.textContent = "AI 正在設計劇情分支並繪製插圖，請耐心等候（可能需要 1-2 分鐘）...";
            } else if (imageMode === "search") {
                gameStatus.textContent = "AI 正在設計劇情分支，並搜尋合適的網路圖片，請稍候...";
            } else {
                gameStatus.textContent = "AI 正在設計劇情分支，請稍候...";
            }
            btnGame.textContent = "生成中...";

            try {
                const resp = await fetch(`/chat/${conversationId}/make_game`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ image_mode: imageMode }),
                });
                const data = await resp.json();
                if (resp.ok) {
                    if (data.image_mode === "upload") {
                        gameStatus.innerHTML =
                            `✅ 劇情已經生成好了！接下來請前往上傳頁面，AI 會告訴你每個場景建議放什麼圖片：<br>` +
                            `<a href="/game/${data.game_id}/upload">📤 前往上傳圖片</a>`;
                    } else {
                        gameStatus.innerHTML =
                            `✅ 遊戲已生成！<a href="/game/${data.game_id}" target="_blank">▶ 點此開始遊玩</a>`;
                    }
                } else {
                    gameStatus.textContent = "⚠️ " + (data.error || "生成失敗");
                }
            } catch (err) {
                gameStatus.textContent = "⚠️ 連線發生錯誤，請稍後再試";
            } finally {
                btnGame.disabled = false;
                btnGame.textContent = "🎮 生成互動遊戲";
            }
        });
    }

    // ---------------- AI 語音回覆（文字轉語音） ----------------
    // 使用瀏覽器內建的 Web Speech API，完全免費，不需要額外的 API 金鑰。
    // 相容性：Chrome / Edge 支援度最好；Firefox / Safari 有可能語音選項較少或效果不同。
    function speakText(text) {
        if (!toggleAiVoice || !toggleAiVoice.checked) return;
        if (!("speechSynthesis" in window)) {
            console.warn("這個瀏覽器不支援語音合成 (speechSynthesis)");
            return;
        }
        // 如果前一句還在講，先停止，避免多句話疊在一起
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "zh-TW";
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }

    // ---------------- 使用者語音輸入（語音轉文字） ----------------
    // 使用瀏覽器內建的 Web Speech API (SpeechRecognition)，完全免費。
    // 注意：目前只有 Chrome / Edge（桌面版與 Android 版）支援較完整，
    // Firefox 與部分 Safari 版本不支援語音輸入，按下麥克風會顯示提示訊息。
    if (btnMic) {
        const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognitionClass) {
            btnMic.addEventListener("click", function () {
                voiceStatus.textContent = "⚠️ 這個瀏覽器不支援語音輸入，建議改用 Chrome 或 Edge 瀏覽器。";
            });
            window.isChatVoiceInputActive = function () {
                return false;
            };
            window.stopChatVoiceInput = function () {};
        } else {
            const recognition = new SpeechRecognitionClass();
            recognition.lang = "zh-TW";
            recognition.continuous = true; // 持續聆聽，講話中間停頓不會自動結束
            recognition.interimResults = true; // 需要即時的暫時結果，才能判斷「使用者是不是還在講」
            recognition.maxAlternatives = 1;

            let isListening = false;
            let finalizedText = ""; // 目前已經確定的語音內容（累積）
            let awaitingConfirmation = false; // 是否正在等待使用者回答「你說完了嗎？」
            let silenceTimer = null;

            const SILENCE_WAIT_MS = 3000; // 停頓多久後，AI 開口詢問是否說完
            const CONFIRM_WAIT_MS = 4000; // 詢問之後，再等多久沒回應就直接視為說完

            function clearSilenceTimer() {
                if (silenceTimer) {
                    clearTimeout(silenceTimer);
                    silenceTimer = null;
                }
            }

            function isAffirmative(text) {
                const t = text.replace(/[，。！？、\s]/g, "");
                const yesWords = [
                    "是的", "是啊", "對啊", "對的", "沒了", "沒有了", "說完了", "講完了",
                    "結束了", "好了", "可以了", "就這樣", "嗯對", "对", "是",
                ];
                return yesWords.some((w) => t.includes(w));
            }

            function askIfFinished() {
                const question = "請問你說完了嗎？如果說完了，我就開始回覆你囉。";
                addBubble("ai", question);
                speakText(question);
                voiceStatus.textContent = "🤔 AI 正在等你回答「說完了」或繼續說下去...";
            }

            function finalizeAndSend() {
                clearSilenceTimer();
                awaitingConfirmation = false;
                const finalMessage = finalizedText.trim();
                finalizedText = "";
                chatInput.value = finalMessage;
                // 注意：這裡不呼叫 recognition.stop()，讓麥克風繼續聆聽下一輪對話，
                // 使用者不需要每講完一句就再按一次麥克風才能繼續講下一句。
                if (finalMessage && chatForm) {
                    if (chatForm.requestSubmit) {
                        chatForm.requestSubmit();
                    } else {
                        chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
                    }
                }
            }

            function resetSilenceTimer() {
                clearSilenceTimer();
                silenceTimer = setTimeout(function () {
                    if (!finalizedText.trim()) return; // 使用者根本還沒說話，不用問

                    if (!awaitingConfirmation) {
                        awaitingConfirmation = true;
                        askIfFinished();
                        // 問完之後多給一點時間；如果還是沒回應，就直接視為說完並送出
                        silenceTimer = setTimeout(function () {
                            if (awaitingConfirmation) finalizeAndSend();
                        }, CONFIRM_WAIT_MS);
                    }
                }, SILENCE_WAIT_MS);
            }

            recognition.addEventListener("start", function () {
                isListening = true;
                finalizedText = "";
                awaitingConfirmation = false;
                btnMic.classList.add("listening");
                btnMic.textContent = "🔴";
                voiceStatus.textContent = "🎙️ 聆聽中，請開始說話（中間停頓沒關係，我會等你）...";
            });

            recognition.addEventListener("result", function (event) {
                let interim = "";
                let newFinal = "";

                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        newFinal += transcript;
                    } else {
                        interim += transcript;
                    }
                }

                resetSilenceTimer();

                if (awaitingConfirmation && newFinal) {
                    // 這句話是在回答「你說完了嗎？」
                    if (isAffirmative(newFinal)) {
                        finalizeAndSend();
                        return;
                    }
                    // 不是肯定回覆，當作繼續講內容，接著累積下去
                    awaitingConfirmation = false;
                    finalizedText += newFinal;
                    chatInput.value = finalizedText;
                    voiceStatus.textContent = "繼續聆聽中...";
                    return;
                }

                if (newFinal) {
                    finalizedText += newFinal;
                }
                chatInput.value = finalizedText + interim;

                if (!awaitingConfirmation) {
                    voiceStatus.textContent = finalizedText || interim
                        ? "🎙️ 聆聽中：「" + (finalizedText + interim) + "」"
                        : "🎙️ 聆聽中，請開始說話...";
                }
            });

            recognition.addEventListener("error", function (event) {
                let msg = "語音辨識發生錯誤";
                if (event.error === "not-allowed" || event.error === "service-not-allowed") {
                    msg = "⚠️ 沒有取得麥克風權限，請在瀏覽器設定中允許使用麥克風";
                } else if (event.error === "no-speech") {
                    // 持續聆聽模式下，短暫沒聲音是正常的，不當作錯誤顯示，靠停頓計時器處理即可
                    return;
                }
                voiceStatus.textContent = msg;
            });

            recognition.addEventListener("end", function () {
                isListening = false;
                awaitingConfirmation = false;
                clearSilenceTimer();
                btnMic.classList.remove("listening");
                btnMic.textContent = "🎤";
            });

            function actuallyStartMic() {
                voiceStatus.textContent = "";
                finalizedText = "";
                awaitingConfirmation = false;
                try {
                    recognition.start();
                } catch (err) {
                    voiceStatus.textContent = "⚠️ 無法啟動麥克風，請稍後再試";
                }
            }

            const micMousePrompt = document.getElementById("mic-mouse-prompt");

            btnMic.addEventListener("click", function () {
                if (isListening) {
                    recognition.stop();
                    return;
                }

                // 記住「切換前」語音控制頁面是不是開著的，這是唯一需要詢問滑鼠模式的情況：
                // 因為語音控制頁面本身可以用「空中滑鼠／一般滑鼠」語音指令操作，
                // 一旦被語音輸入取代（兩者互斥），使用者就沒辦法再用講的切換滑鼠了，所以主動問一次。
                const wasVoiceControlActive = !!(window.isVoiceControlActive && window.isVoiceControlActive());

                // 跟「語音控制頁面」互斥，一次只能開一個
                if (wasVoiceControlActive && window.stopVoiceControl) {
                    window.stopVoiceControl();
                }

                if (wasVoiceControlActive && micMousePrompt) {
                    micMousePrompt.style.display = "block";
                } else {
                    actuallyStartMic();
                }
            });

            if (micMousePrompt) {
                const choiceGesture = document.getElementById("mic-choice-gesture");
                const choiceNormal = document.getElementById("mic-choice-normal");

                function hideMicPrompt() {
                    micMousePrompt.style.display = "none";
                }

                if (choiceGesture) {
                    choiceGesture.addEventListener("click", async function () {
                        hideMicPrompt();
                        if (window.startGestureMouseViaVoice) await window.startGestureMouseViaVoice();
                        actuallyStartMic();
                    });
                }
                if (choiceNormal) {
                    choiceNormal.addEventListener("click", function () {
                        hideMicPrompt();
                        if (window.stopGestureMouseNow) window.stopGestureMouseNow();
                        actuallyStartMic();
                    });
                }
            }

            window.isChatVoiceInputActive = function () {
                return isListening;
            };
            window.stopChatVoiceInput = function () {
                if (isListening) recognition.stop();
            };
        }
    }
})();
