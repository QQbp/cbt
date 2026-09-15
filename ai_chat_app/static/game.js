(function () {
    const dataEl = document.getElementById("game-data");
    if (!dataEl) return;

    let gameData;
    try {
        gameData = JSON.parse(dataEl.textContent);
    } catch (err) {
        document.getElementById("game-text").textContent = "⚠️ 遊戲資料讀取失敗。";
        return;
    }

    const titleEl = document.getElementById("game-title");
    const imageEl = document.getElementById("game-image");
    const creditEl = document.getElementById("game-image-credit");
    const textEl = document.getElementById("game-text");
    const choicesEl = document.getElementById("game-choices");
    const restartBtn = document.getElementById("game-restart");

    function renderNode(nodeId) {
        const node = gameData.nodes[nodeId];
        if (!node) {
            textEl.textContent = "⚠️ 找不到劇情節點，遊戲資料可能有誤。";
            return;
        }

        if (node.image_data) {
            imageEl.src = node.image_data;
            imageEl.style.display = "block";
        } else {
            imageEl.style.display = "none";
        }

        // 如果這張圖是從 Unsplash 搜尋來的，依規定顯示攝影師出處
        creditEl.textContent = "";
        if (node.image_credit_text) {
            if (node.image_credit_url) {
                const a = document.createElement("a");
                a.href = node.image_credit_url;
                a.target = "_blank";
                a.rel = "noopener";
                a.textContent = node.image_credit_text;
                creditEl.appendChild(a);
            } else {
                creditEl.textContent = node.image_credit_text;
            }
            creditEl.style.display = "block";
        } else {
            creditEl.style.display = "none";
        }

        textEl.textContent = node.text || "";
        choicesEl.innerHTML = "";

        const isEnding = node.is_ending || !node.choices || node.choices.length === 0;

        if (isEnding) {
            const endTag = document.createElement("div");
            endTag.className = "ending-tag";
            endTag.textContent = "🏁 " + (node.ending_title || "故事結局");
            choicesEl.appendChild(endTag);
            restartBtn.style.display = "inline-block";
        } else {
            restartBtn.style.display = "none";
            node.choices.forEach(function (choice) {
                const btn = document.createElement("button");
                btn.className = "btn-primary choice-btn";
                btn.textContent = choice.text;
                btn.addEventListener("click", function () {
                    renderNode(choice.next);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                });
                choicesEl.appendChild(btn);
            });
        }
    }

    restartBtn.addEventListener("click", function () {
        renderNode(gameData.start_node);
    });

    titleEl.textContent = gameData.title || "互動故事";
    renderNode(gameData.start_node);
})();
