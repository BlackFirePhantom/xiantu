/* ===== 仙途 — 主入口 & 键盘快捷键 ===== */

// ═══════════════ 游戏操作 ═══════════════

function doFight() { socket.emit("fight"); }
function doMeditate() { socket.emit("meditate"); }
function doBreakthrough() { socket.emit("breakthrough"); }
function showSecretRealm() {
    document.getElementById("secret-realm-modal").style.display = "flex";
    socket.emit("get_secret_realm");
}
function showSectBoss() {
    document.getElementById("sect-boss-modal").style.display = "flex";
    socket.emit("get_sect_boss");
}

function exploreSecretRealm() { socket.emit("secret_realm_explore"); }
function challengeSecretRealm() { socket.emit("secret_realm_challenge"); }
function claimSecretRealmSettlement(weekId) { socket.emit("claim_secret_realm_settlement", { week_id: weekId }); }
function challengeSectBoss() { socket.emit("sect_boss_challenge"); }

function sendChat() {
    const input = document.getElementById("chat-input");
    const text = input.value.trim();
    if (text) { socket.emit("chat", { text: text }); input.value = ""; }
}

// ═══════════════ 键盘快捷键 ═══════════════

document.addEventListener("keydown", (e) => {
    // 聊天框聚焦时，只处理 ESC 和回车
    const chatInput = document.getElementById("chat-input");
    if (document.activeElement === chatInput) {
        if (e.key === "Escape") { chatInput.blur(); e.preventDefault(); }
        return; // Enter 由 chat-input 的 keypress 处理
    }

    // ESC 关闭所有弹窗
    if (e.key === "Escape") {
        if (isAnyModalOpen()) {
            closeAllModals();
            e.preventDefault();
        }
        return;
    }

    // 奇遇弹窗打开时，1/2/3 选择选项
    if (currentForture) {
        const idx = parseInt(e.key) - 1;
        if (idx >= 0 && idx < currentForture.choices.length) {
            socket.emit("fortune_choice", { event_id: currentForture.event_id, choice: currentForture.choices[idx].index });
            document.getElementById("fortune-popup").style.display = "none";
            currentForture = null;
            e.preventDefault();
        }
        return;
    }

    // 任何弹窗打开时不处理快捷键
    if (isAnyModalOpen()) return;

    // 战斗中快捷键
    if (combatState) {
        switch (e.key.toLowerCase()) {
            case " ": // 空格 - 普攻
                sendFightAction("attack");
                e.preventDefault();
                break;
            case "q": // Q - 防御
                sendFightAction("defend");
                e.preventDefault();
                break;
            case "e": // E - 逃跑
                sendFightAction("flee");
                e.preventDefault();
                break;
            case "1": case "2": case "3": case "4": case "5":
            case "6": case "7": case "8": case "9":
                {
                    const idx = parseInt(e.key) - 1;
                    const skillBtns = document.querySelectorAll("#combat-actions .btn-skill");
                    if (idx < skillBtns.length && !skillBtns[idx].disabled) {
                        skillBtns[idx].click();
                        e.preventDefault();
                    }
                }
                break;
        }
        return;
    }

    // 游戏快捷键
    switch (e.key.toLowerCase()) {
        case "f": // F - 斩妖
            doFight();
            e.preventDefault();
            break;
        case "m": // M - 打坐
            doMeditate();
            e.preventDefault();
            break;
        case "b": // B - 突破
            doBreakthrough();
            e.preventDefault();
            break;
        case "t": // T - 功法
            showPanel("techniques");
            e.preventDefault();
            break;
        case "j": // J - 经脉
            showPanel("meridians");
            e.preventDefault();
            break;
        case "l": // L - 天骄榜
            showLeaderboard();
            e.preventDefault();
            break;
        case "1": case "2": case "3": case "4": case "5":
        case "6": case "7": case "8": case "9": // 数字键移动
            {
                const connBtns = document.querySelectorAll("#connections .conn-btn");
                const idx = parseInt(e.key) - 1;
                if (idx < connBtns.length) {
                    connBtns[idx].click();
                    e.preventDefault();
                }
            }
            break;
    }
});

// ═══════════════ 初始化 ═══════════════

document.addEventListener("DOMContentLoaded", () => {
    // 聊天回车发送
    document.getElementById("chat-input").addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendChat();
    });

    // ESC 关闭弹窗（点击遮罩层也关闭）
    document.querySelectorAll(".modal").forEach(modal => {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) modal.style.display = "none";
        });
    });

    // 快捷键提示
    addLog("快捷键：F=斩妖 M=打坐 B=突破 T=功法 J=经脉 L=天骄榜 1-9=移动 ESC=关闭", "system");
    
    // 初始化装备拖放交互
    if (typeof initDragAndDrop === "function") {
        initDragAndDrop();
    }
});
