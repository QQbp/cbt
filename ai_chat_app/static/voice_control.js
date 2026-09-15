/*
 * 語音控制頁面功能
 * 開啟後會持續聆聽，講出特定指令詞就會自動觸發對應的操作
 * （導覽、切換對話模式、按下對話頁面的操作按鈕、切換空中滑鼠等）。
 *
 * 跟「語音輸入訊息」互斥：兩者一次只能開啟一個，避免使用者講話
 * 同時被誤認成指令又被打進聊天輸入框。
 *
 * 開啟後會持續生效到你自己關閉為止，切換頁面會自動接續開啟
 * （用 localStorage 記住狀態，跟空中滑鼠的做法一致）。
 */
(function () {
    let recognition = null;
    let active = false;
    let manuallyStopped = false;

    const STORAGE_KEY = "voiceControlActive";

    function saveState(isActive) {
        try {
            localStorage.setItem(STORAGE_KEY, isActive ? "true" : "false");
        } catch (e) {
            // 忽略：部分瀏覽器隱私模式可能擋掉 localStorage
        }
    }

    function loadState() {
        try {
            return localStorage.getItem(STORAGE_KEY) === "true";
        } catch (e) {
            return false;
        }
    }

    function getSpeechRecognitionClass() {
        return window.SpeechRecognition || window.webkitSpeechRecognition;
    }

    function setStatus(text) {
        const el = document.getElementById("voice-control-status");
        if (el) el.textContent = text;
    }

    function clickIfExists(id) {
        const el = document.getElementById(id);
        if (el && !el.disabled) {
            el.click();
            return true;
        }
        return false;
    }

    function goTo(url) {
        if (url) window.location.href = url;
    }

    function handleCommand(rawText) {
        const text = rawText.replace(/[，。！？、\s]/g, "");
        console.log("[語音控制] 聽到指令：", rawText);

        const routes = window.APP_ROUTES || {};

        const commandTable = [
            { keywords: ["登出"], action: () => goTo(routes.logout) },
            { keywords: ["回首頁", "首頁", "開始對話"], action: () => goTo(routes.home) },
            { keywords: ["歷史紀錄", "歷史記錄"], action: () => goTo(routes.history) },
            {
                keywords: ["管理後台"],
                action: () => {
                    if (routes.admin) goTo(routes.admin);
                    else setStatus("⚠️ 你沒有管理者權限，無法使用這個指令");
                },
            },
            {
                keywords: ["日記模式"],
                action: () => {
                    if (!clickIfExists("mode-btn-diary")) setStatus("⚠️ 目前頁面沒有這個功能");
                },
            },
            {
                keywords: ["主題模式"],
                action: () => {
                    if (!clickIfExists("mode-btn-topic")) setStatus("⚠️ 目前頁面沒有這個功能");
                },
            },
            {
                keywords: ["分析這段對話", "分析對話", "分析"],
                action: () => {
                    if (!clickIfExists("btn-analyze")) setStatus("⚠️ 目前頁面沒有這個功能");
                },
            },
            {
                keywords: ["生成互動遊戲", "生成遊戲"],
                action: () => {
                    if (!clickIfExists("btn-game")) setStatus("⚠️ 目前頁面沒有這個功能");
                },
            },
            {
                keywords: ["生成故事"],
                action: () => {
                    if (!clickIfExists("btn-story")) setStatus("⚠️ 目前頁面沒有這個功能");
                },
            },
            {
                keywords: ["結束對話"],
                action: () => {
                    if (!clickIfExists("btn-end")) setStatus("⚠️ 目前頁面沒有這個功能");
                },
            },
            {
                keywords: ["空中滑鼠"],
                action: () => {
                    if (window.startGestureMouseViaVoice) window.startGestureMouseViaVoice();
                },
            },
            {
                keywords: ["一般滑鼠", "關閉空中滑鼠"],
                action: () => {
                    if (window.stopGestureMouseNow) window.stopGestureMouseNow();
                },
            },
        ];

        for (const cmd of commandTable) {
            if (cmd.keywords.some((kw) => text.includes(kw))) {
                cmd.action();
                return;
            }
        }
        setStatus(`🤔 沒有聽懂指令：「${rawText}」`);
    }

    function createRecognition() {
        const SpeechRecognitionClass = getSpeechRecognitionClass();
        if (!SpeechRecognitionClass) return null;

        const r = new SpeechRecognitionClass();
        r.lang = "zh-TW";
        r.continuous = true;
        r.interimResults = false;
        r.maxAlternatives = 1;

        r.addEventListener("result", (event) => {
            const lastResult = event.results[event.results.length - 1];
            if (lastResult && lastResult.isFinal) {
                handleCommand(lastResult[0].transcript);
            }
        });

        r.addEventListener("error", (event) => {
            console.error("[語音控制] 錯誤：", event.error);
            if (event.error === "not-allowed" || event.error === "service-not-allowed") {
                setStatus("⚠️ 沒有取得麥克風權限，請允許瀏覽器使用麥克風");
                window.stopVoiceControl();
            }
            // 其他像 no-speech 之類的小狀況忽略即可，靠 onend 自動重新開始聆聽
        });

        r.addEventListener("end", () => {
            if (active && !manuallyStopped) {
                // 瀏覽器有時候會在安靜一段時間後自動停止辨識，這裡自動重啟，維持「持續聆聽」的效果
                try {
                    r.start();
                } catch (e) {
                    // 忽略「已經在執行中」之類的例外
                }
            }
        });

        return r;
    }

    window.isVoiceControlActive = function () {
        return active;
    };

    window.stopVoiceControl = function () {
        manuallyStopped = true;
        active = false;
        if (recognition) {
            try {
                recognition.stop();
            } catch (e) {
                // 忽略停止時的例外
            }
        }
        setStatus("");
        saveState(false);
        const btn = document.getElementById("btn-voice-control");
        if (btn) {
            btn.textContent = "🎙️ 語音控制頁面";
            btn.classList.remove("active-toggle");
        }
    };

    window.startVoiceControl = function () {
        const SpeechRecognitionClass = getSpeechRecognitionClass();
        if (!SpeechRecognitionClass) {
            setStatus("⚠️ 這個瀏覽器不支援語音辨識，建議改用 Chrome 或 Edge 瀏覽器");
            return false;
        }

        // 跟聊天頁的「語音輸入訊息」互斥，一次只能開一個
        if (window.isChatVoiceInputActive && window.isChatVoiceInputActive() && window.stopChatVoiceInput) {
            window.stopChatVoiceInput();
        }

        manuallyStopped = false;
        recognition = createRecognition();
        if (!recognition) {
            setStatus("⚠️ 無法建立語音辨識，請確認瀏覽器支援度");
            return false;
        }

        try {
            recognition.start();
        } catch (e) {
            console.error("[語音控制] 啟動失敗：", e);
            setStatus("⚠️ 語音控制啟動失敗，詳細內容已印在瀏覽器主控台");
            return false;
        }

        active = true;
        setStatus("🎙️ 語音控制已啟動，可以說「登出」「回首頁」「日記模式」「分析」等指令");
        saveState(true);
        const btn = document.getElementById("btn-voice-control");
        if (btn) {
            btn.textContent = "🎙️ 關閉語音控制";
            btn.classList.add("active-toggle");
        }
        return true;
    };

    window.toggleVoiceControl = function () {
        if (active) {
            window.stopVoiceControl();
        } else {
            window.startVoiceControl();
        }
    };

    // 頁面載入時，如果之前是開著的、而且這個頁面有登入（看得到按鈕），就自動接續開啟
    (function restoreIfNeeded() {
        const wasActive = loadState();
        if (!wasActive) return;
        const btn = document.getElementById("btn-voice-control");
        if (!btn) return; // 沒登入看不到按鈕，不要偷偷開麥克風
        window.startVoiceControl();
    })();
})();
