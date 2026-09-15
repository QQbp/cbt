/*
 * 空中滑鼠（Air Mouse）功能
 * 用 MediaPipe Hands 偵測雙手，並依照使用者選擇的分工設定：
 *   - 「移動手」：只負責控制虛擬游標位置，這隻手自己握不握拳都不影響點擊判定
 *   - 「點擊手」：只負責觸發滑鼠按下/放開（放開時視為一次點擊），這隻手的位置不影響游標
 * 分工是依照「畫面上看起來的左右邊」來指定（開始使用前會請你選擇），
 * 不用管 MediaPipe 判斷的解剖學左右手，比較直覺、也不會被鏡像畫面搞混。
 *
 * 只有按下導覽列的「🖐️ 空中滑鼠」按鈕時才會開啟攝影機，
 * 再按一次就會完全關閉攝影機與辨識，不會偷偷佔用鏡頭。
 *
 * MediaPipe 的函式庫比較大，所以採用「第一次啟用時才動態載入」，
 * 平常瀏覽網站不會多花這個載入時間。
 */
(function () {
    let handsInstance = null;
    let cameraInstance = null;
    let isMouseDown = false;
    let smoothX = 0;
    let smoothY = 0;
    let active = false;
    let scriptsLoaded = false;
    let lastLoggedHandsCount = -1;

    // 分工設定："left-move" = 畫面左邊的手移動、右邊的手點擊；"right-move" = 相反
    let handRoleMode = "left-move";

    // 用 localStorage 記住「現在是不是開著空中滑鼠」跟「分工設定」，
    // 這樣切換到其他頁面時，可以自動接續開啟，不用每個頁面都重新選一次。
    const STORAGE_ACTIVE_KEY = "gestureMouseActive";
    const STORAGE_ROLE_KEY = "gestureMouseHandRole";

    function saveGestureMouseState(isActive, roleMode) {
        try {
            localStorage.setItem(STORAGE_ACTIVE_KEY, isActive ? "true" : "false");
            if (roleMode) localStorage.setItem(STORAGE_ROLE_KEY, roleMode);
        } catch (e) {
            // 部分瀏覽器的隱私模式可能會擋掉 localStorage，忽略即可，只是不會記住狀態
        }
    }

    function loadGestureMouseState() {
        try {
            return {
                wasActive: localStorage.getItem(STORAGE_ACTIVE_KEY) === "true",
                roleMode: localStorage.getItem(STORAGE_ROLE_KEY) || "left-move",
            };
        } catch (e) {
            return { wasActive: false, roleMode: "left-move" };
        }
    }

    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const s = document.createElement("script");
            s.src = src;
            s.crossOrigin = "anonymous";
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }

    async function ensureScriptsLoaded() {
        if (scriptsLoaded) return;
        await loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js");
        await loadScript("https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js");
        scriptsLoaded = true;
    }

    // 判斷單一手掌是否握拳：食指指尖[8] 到手腕[0] 的距離，小於門檻視為握拳
    function checkIsGrip(landmarks) {
        const indexTip = landmarks[8];
        const wrist = landmarks[0];
        const dist = Math.hypot(indexTip.x - wrist.x, indexTip.y - wrist.y);
        return dist < 0.35;
    }

    // 發送網頁原生滑鼠事件，讓虛擬游標可以真的點擊到畫面上的按鈕/連結
    function dispatchMouseEvent(type, x, y) {
        const target = document.elementFromPoint(x, y) || document.body;
        const evt = new MouseEvent(type, {
            clientX: x,
            clientY: y,
            bubbles: true,
            cancelable: true,
            view: window,
        });
        target.dispatchEvent(evt);
    }

    // 計算某隻手在「鏡像後畫面」上的水平位置（跟游標座標算法一致），用來判斷這隻手在螢幕上是偏左還是偏右
    function onscreenX(landmarks) {
        return (1 - landmarks[0].x) * window.innerWidth;
    }

    function onResults(results, cursor) {
        const handsCount = results.multiHandLandmarks ? results.multiHandLandmarks.length : 0;

        // 除錯用：即時顯示目前偵測到幾隻手，只有數字變動時才更新，避免畫面一直閃
        if (handsCount !== lastLoggedHandsCount) {
            lastLoggedHandsCount = handsCount;
            console.log(`[空中滑鼠] 目前偵測到 ${handsCount} 隻手`);
            const debugEl = document.getElementById("gesture-debug");
            if (debugEl) debugEl.textContent = `👀 目前偵測到 ${handsCount} 隻手（需要剛好 2 隻才會顯示游標）`;
        }

        // 必須「兩隻手同時在畫面中」才會啟動操作，避免只有一隻手時誤觸
        if (handsCount === 2) {
            cursor.style.display = "block";

            const hand1 = results.multiHandLandmarks[0];
            const hand2 = results.multiHandLandmarks[1];

            // 依照畫面上的左右位置，決定哪隻手是「螢幕左邊的手」、哪隻是「螢幕右邊的手」
            const hand1X = onscreenX(hand1);
            const hand2X = onscreenX(hand2);
            const leftOnscreenHand = hand1X <= hand2X ? hand1 : hand2;
            const rightOnscreenHand = hand1X <= hand2X ? hand2 : hand1;

            // 依照使用者選擇的分工設定，固定指定「移動手」跟「點擊手」
            let moveHand, clickHand;
            if (handRoleMode === "right-move") {
                moveHand = rightOnscreenHand;
                clickHand = leftOnscreenHand;
            } else {
                moveHand = leftOnscreenHand;
                clickHand = rightOnscreenHand;
            }

            // 游標位置永遠由「移動手」的食指指尖決定，這隻手自己握不握拳都不影響
            const indexTip = moveHand[8];
            const rawX = (1 - indexTip.x) * window.innerWidth; // 水平鏡像，符合直覺
            const rawY = indexTip.y * window.innerHeight;

            smoothX += (rawX - smoothX) * 0.3;
            smoothY += (rawY - smoothY) * 0.3;
            cursor.style.left = `${smoothX}px`;
            cursor.style.top = `${smoothY}px`;

            // 點擊判定永遠只看「點擊手」是否握拳，跟移動手的狀態無關
            const clickHandIsGrip = checkIsGrip(clickHand);

            if (clickHandIsGrip && !isMouseDown) {
                isMouseDown = true;
                cursor.classList.add("active");
                dispatchMouseEvent("mousedown", smoothX, smoothY);
            } else if (!clickHandIsGrip && isMouseDown) {
                isMouseDown = false;
                cursor.classList.remove("active");
                dispatchMouseEvent("mouseup", smoothX, smoothY);
                dispatchMouseEvent("click", smoothX, smoothY);
            }

            if (isMouseDown) {
                dispatchMouseEvent("mousemove", smoothX, smoothY);
            }
        } else {
            // 不是剛好兩隻手時，隱藏游標、強制放開按鍵，確保安全、避免誤觸
            cursor.style.display = "none";
            if (isMouseDown) {
                isMouseDown = false;
                cursor.classList.remove("active");
                dispatchMouseEvent("mouseup", smoothX, smoothY);
            }
        }
    }

    async function startGestureMouse() {
        const statusEl = document.getElementById("gesture-status");
        if (statusEl) statusEl.textContent = "正在啟動攝影機與手勢辨識...";

        try {
            await ensureScriptsLoaded();
        } catch (err) {
            console.error("空中滑鼠套件載入失敗：", err);
            if (statusEl) statusEl.textContent = "⚠️ 無法載入手勢辨識套件，請確認網路連線（詳細內容已印在瀏覽器主控台 Console）";
            return false;
        }

        const videoElement = document.getElementById("gesture-webcam");
        const cursor = document.getElementById("virtual-cursor");
        const container = document.getElementById("gesture-container");

        try {
            if (typeof Hands === "undefined" || typeof Camera === "undefined") {
                throw new Error("MediaPipe 套件沒有正確載入（Hands 或 Camera 未定義）");
            }

            handsInstance = new Hands({
                locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
            });
            handsInstance.setOptions({
                maxNumHands: 2,
                modelComplexity: 1,
                minDetectionConfidence: 0.7,
                minTrackingConfidence: 0.7,
            });
            handsInstance.onResults((results) => onResults(results, cursor));

            cameraInstance = new Camera(videoElement, {
                onFrame: async () => {
                    await handsInstance.send({ image: videoElement });
                },
                width: 320,
                height: 240,
            });

            await cameraInstance.start();
        } catch (err) {
            console.error("空中滑鼠啟動失敗：", err);
            if (statusEl) {
                statusEl.textContent = `⚠️ 啟動失敗：${err.message || err}（詳細內容已印在瀏覽器主控台 Console）`;
            }
            return false;
        }

        container.style.display = "block";
        if (statusEl) {
            const moveSide = handRoleMode === "right-move" ? "右邊" : "左邊";
            const clickSide = handRoleMode === "right-move" ? "左邊" : "右邊";
            statusEl.textContent = `✅ 空中滑鼠已啟動：畫面${moveSide}的手移動游標，${clickSide}的手握拳點擊`;
        }
        active = true;
        return true;
    }

    function stopGestureMouse() {
        if (cameraInstance) {
            try {
                cameraInstance.stop();
            } catch (e) {
                // 忽略停止時的例外
            }
        }
        const videoElement = document.getElementById("gesture-webcam");
        if (videoElement && videoElement.srcObject) {
            videoElement.srcObject.getTracks().forEach((track) => track.stop());
            videoElement.srcObject = null;
        }
        const cursor = document.getElementById("virtual-cursor");
        const container = document.getElementById("gesture-container");
        if (cursor) {
            cursor.style.display = "none";
            cursor.classList.remove("active");
        }
        if (container) container.style.display = "none";
        const statusEl = document.getElementById("gesture-status");
        if (statusEl) statusEl.textContent = "";
        const debugEl = document.getElementById("gesture-debug");
        if (debugEl) debugEl.textContent = "";
        lastLoggedHandsCount = -1;
        isMouseDown = false;
        active = false;
        saveGestureMouseState(false);
    }

    function closeGestureMenu() {
        const menu = document.getElementById("gesture-menu");
        if (menu) menu.style.display = "none";
    }

    // 給其他功能（語音控制、語音輸入）查詢/操作用的公開介面
    window.isGestureMouseActive = function () {
        return active;
    };

    // 直接啟動空中滑鼠（不透過選單），用上次選過的分工設定（沒選過就用預設）。
    // 給語音指令「空中滑鼠」、以及語音輸入時的詢問視窗使用。
    window.startGestureMouseViaVoice = async function () {
        if (active) return true;

        const { roleMode } = loadGestureMouseState();
        handRoleMode = roleMode;

        const toggleBtn = document.getElementById("btn-gesture-mouse");
        if (toggleBtn) {
            toggleBtn.disabled = true;
            toggleBtn.textContent = "啟動中...";
        }

        const ok = await startGestureMouse();

        if (toggleBtn) {
            toggleBtn.disabled = false;
            toggleBtn.textContent = ok ? "🖐️ 關閉空中滑鼠" : "🖐️ 空中滑鼠";
            toggleBtn.classList.toggle("active-toggle", ok);
        }

        saveGestureMouseState(ok, handRoleMode);
        return ok;
    };

    // 直接關閉空中滑鼠（不透過選單），給語音指令「一般滑鼠」使用
    window.stopGestureMouseNow = function () {
        if (!active) return;
        stopGestureMouse();
        const toggleBtn = document.getElementById("btn-gesture-mouse");
        if (toggleBtn) {
            toggleBtn.textContent = "🖐️ 空中滑鼠";
            toggleBtn.classList.remove("active-toggle");
        }
    };

    // 按下導覽列的主按鈕：尚未啟動時 → 打開分工選單；已啟動時 → 直接關閉
    window.toggleGestureMouse = function () {
        if (active) {
            stopGestureMouse();
            const toggleBtn = document.getElementById("btn-gesture-mouse");
            if (toggleBtn) {
                toggleBtn.textContent = "🖐️ 空中滑鼠";
                toggleBtn.classList.remove("active-toggle");
            }
            return;
        }

        const menu = document.getElementById("gesture-menu");
        if (menu) {
            const isOpen = menu.style.display === "block";
            menu.style.display = isOpen ? "none" : "block";
        }
    };

    // 選單裡按下「開始」：套用選擇的分工設定，關閉選單，正式啟動攝影機
    window.confirmGestureMouseStart = async function () {
        const selected = document.querySelector('input[name="gesture-hand-role"]:checked');
        handRoleMode = selected ? selected.value : "left-move";
        closeGestureMenu();

        const toggleBtn = document.getElementById("btn-gesture-mouse");
        if (toggleBtn) {
            toggleBtn.disabled = true;
            toggleBtn.textContent = "啟動中...";
        }

        const ok = await startGestureMouse();

        if (toggleBtn) {
            toggleBtn.disabled = false;
            toggleBtn.textContent = ok ? "🖐️ 關閉空中滑鼠" : "🖐️ 空中滑鼠";
            toggleBtn.classList.toggle("active-toggle", ok);
        }

        saveGestureMouseState(ok, handRoleMode);
    };

    // 頁面載入時，如果使用者之前是開著空中滑鼠、還沒有自己關閉，就自動接續開啟，
    // 不需要每切換一個頁面就重新選一次分工、重新按開始。
    (async function restoreGestureMouseIfNeeded() {
        const { wasActive, roleMode } = loadGestureMouseState();
        if (!wasActive) return;

        const toggleBtn = document.getElementById("btn-gesture-mouse");
        if (!toggleBtn) {
            // 這個頁面沒有登入、看不到切換按鈕（例如登入頁），就不要偷偷啟動攝影機，
            // 不然使用者會找不到地方關閉它。
            return;
        }

        handRoleMode = roleMode;

        // 讓選單裡的分工選項顯示成使用者上次選擇的那個
        const radios = document.querySelectorAll('input[name="gesture-hand-role"]');
        radios.forEach((r) => {
            r.checked = r.value === roleMode;
        });

        toggleBtn.disabled = true;
        toggleBtn.textContent = "啟動中...";

        const ok = await startGestureMouse();

        toggleBtn.disabled = false;
        toggleBtn.textContent = ok ? "🖐️ 關閉空中滑鼠" : "🖐️ 空中滑鼠";
        toggleBtn.classList.toggle("active-toggle", ok);

        // 如果這次自動啟動失敗（例如攝影機被其他分頁占用），就不要一直卡在「以為是開著」的狀態
        if (!ok) saveGestureMouseState(false);
    })();
})();
