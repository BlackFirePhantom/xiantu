/* ===== 仙途 — Socket.IO 连接与状态管理 ===== */

const socket = io();
let gameState = null;
let currentForture = null;

// ═══════════════ Socket 事件绑定 ═══════════════

socket.on("connect", () => socket.emit("get_state"));

socket.on("game_state", (data) => {
    gameState = data;
    renderState(data);
});

socket.on("need_create", () => { window.location.href = "/create"; });

socket.on("game_msg", (data) => addLog(data.text, data.type || "info"));

// 回合制战斗事件
socket.on("combat_start", (data) => {
    showCombatPanel(data);
});
socket.on("combat_round", (data) => {
    updateCombatRound(data);
});
socket.on("combat_end", (data) => {
    endCombat(data);
});

socket.on("system_msg", (data) => addLog(data.text, "system"));
socket.on("player_moved", (data) => addLog(`${data.player} 御剑前往了 ${data.to_name}`, "player-move"));
socket.on("chat_msg", (data) => addChat(data.from, data.text));
socket.on("leaderboard", (data) => renderLeaderboard(data.data));
socket.on("secret_realm_state", (data) => renderSecretRealm(data));
socket.on("sect_boss_state", (data) => renderSectBoss(data));
socket.on("techniques_list", (data) => renderTechniques(data));
socket.on("meridians_list", (data) => renderMeridians(data));
socket.on("forge_recipes", (data) => renderForgePanel(data));
socket.on("forge_log", (data) => {
    data.log.forEach((line) => addLog(line, data.success ? "shop" : "error"));
});
socket.on("afk_status", (data) => {
    const indicator = document.getElementById("afk-indicator");
    if (data.afk) {
        indicator.style.display = "inline";
        indicator.textContent = "[挂机中]";
        addLog("你已进入挂机修炼状态（10分钟无操作自动触发）", "system");
    } else {
        indicator.style.display = "none";
        addLog("你结束了挂机状态，回到正常修炼。", "system");
    }
});
socket.on("afk_tick", (data) => {
    const indicator = document.getElementById("afk-indicator");
    if (indicator.style.display !== "inline") return;
    let msg = `[挂机${data.duration}] 修为+${data.exp}`;
    if (data.drops.length > 0) msg += `，获得${data.drops.join("、")}`;
    addLog(msg, "system");
    socket.emit("get_state");
});
socket.on("npc_detail", (data) => renderNPCDetail(data));

// 物品详情
socket.on("item_detail", (data) => {
    const body = document.getElementById("item-detail-body");
    let html = `<h3 style="color:#8fd4a0;margin-bottom:12px;">${data.name}</h3>`;
    html += `<div style="color:#c8c0b0;font-size:13px;margin-bottom:8px;">${data.desc}</div>`;
    if (data.effect) {
        html += `<div style="color:#7eb8da;font-size:12px;margin-bottom:8px;">${data.effect}</div>`;
    }
    html += '<div style="border-top:1px solid #2a3a32;padding-top:8px;margin-top:8px;">';
    html += '<div style="color:#d4b870;font-size:12px;margin-bottom:4px;">获取途径：</div>';
    data.sources.forEach(s => {
        html += `<div style="color:#6a8a7a;font-size:12px;padding:2px 0;">· ${s}</div>`;
    });
    html += '</div>';
    body.innerHTML = html;
    document.getElementById("item-detail-modal").style.display = "flex";
});

// 奇遇事件
socket.on("fortune_event", (data) => {
    currentForture = data;
    const popup = document.getElementById("fortune-popup");
    document.getElementById("fortune-title").textContent = data.title;
    document.getElementById("fortune-text").textContent = data.text;
    const choicesDiv = document.getElementById("fortune-choices");
    choicesDiv.innerHTML = "";
    data.choices.forEach((c) => {
        const btn = document.createElement("button");
        btn.className = "btn btn-fortune-choice";
        btn.textContent = c.text;
        btn.onclick = () => {
            socket.emit("fortune_choice", { event_id: data.event_id, choice: c.index });
            popup.style.display = "none";
            currentForture = null;
        };
        choicesDiv.appendChild(btn);
    });
    popup.style.display = "block";
});

// 拍卖行事件
socket.on("auction_list", (data) => renderAuctionPanel(data));
socket.on("auction_update", (data) => {
    if (document.getElementById("auction-modal").style.display !== "none") {
        socket.emit("get_auction");
    }
});
socket.on("auction_log", (data) => addLog(data.text, data.type || "shop"));
