/* ===== 仙途 — 前端逻辑 ===== */

const socket = io();
let gameState = null;
let currentForture = null;

// ═══════════════ Socket 事件 ═══════════════

socket.on("connect", () => socket.emit("get_state"));

socket.on("game_state", (data) => {
    gameState = data;
    renderState(data);
});

socket.on("need_create", () => { window.location.href = "/create"; });

socket.on("game_msg", (data) => addLog(data.text, data.type || "info"));

socket.on("fight_log", (data) => {
    data.log.forEach((line) => {
        if (line.startsWith("——")) addLog(line, "fight");
        else if (line.includes("斗法胜利")) addLog(line, "fight-win");
        else if (line.includes("陨落")) addLog(line, "fight-lose");
        else if (line.includes("机缘") || line.includes("获得")) addLog(line, "shop");
        else if (line.includes("损失")) addLog(line, "error");
        else addLog(line, "fight");
    });
});

socket.on("system_msg", (data) => addLog(data.text, "system"));
socket.on("player_moved", (data) => addLog(`${data.player} 御剑前往了 ${data.to_name}`, "player-move"));
socket.on("chat_msg", (data) => addChat(data.from, data.text));
socket.on("leaderboard", (data) => renderLeaderboard(data.data));
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

// ═══════════════ 渲染 ═══════════════

function renderState(s) {
    const c = s.char;
    document.getElementById("char-name").textContent = c.name;
    document.getElementById("char-realm").textContent = c.realm;
    document.getElementById("char-exp").textContent = `${c.exp} / ${c.exp_needed}`;
    document.getElementById("char-hp").textContent = `${c.hp} / ${c.max_hp}`;
    document.getElementById("char-atk").textContent = c.atk;
    document.getElementById("char-def").textContent = c.def;
    document.getElementById("char-gold").textContent = c.gold + " 灵石";
    document.getElementById("char-kills").textContent = c.kills;
    document.getElementById("char-deaths").textContent = c.deaths;
    document.getElementById("char-mult").textContent = c.cultivation_mult + "x";

    // 灵根
    const rootEl = document.getElementById("char-root");
    if (s.spirit_root) {
        rootEl.textContent = s.spirit_root.name + (s.spirit_root.element ? `（${s.spirit_root.element}）` : "");
        rootEl.title = s.spirit_root.desc;
    } else {
        rootEl.textContent = "未觉醒";
    }

    const hpPct = c.max_hp > 0 ? (c.hp / c.max_hp * 100) : 0;
    document.getElementById("hp-bar").style.width = hpPct + "%";

    // 地点
    const loc = s.location;
    document.getElementById("loc-name").textContent = loc.name;
    document.getElementById("loc-desc").textContent = loc.desc;
    const badge = document.getElementById("loc-badge");
    badge.textContent = loc.safe ? "安全" : "险地";
    badge.className = "badge " + (loc.safe ? "badge-safe" : "badge-danger");

    const npcArea = document.getElementById("npc-area");
    if (loc.npc) {
        npcArea.style.display = "block";
        document.getElementById("npc-name").textContent = loc.npc;
        document.getElementById("npc-dialog").textContent = loc.npc_dialog;
    } else {
        npcArea.style.display = "none";
    }

    document.getElementById("btn-fight").style.display = loc.safe ? "none" : "inline-block";
    document.getElementById("btn-rest").style.display = loc.safe ? "inline-block" : "none";

    // 突破按钮
    const btnBT = document.getElementById("btn-breakthrough");
    if (c.exp_needed !== "-" && c.exp >= c.exp_needed && c.level < 15) {
        btnBT.style.display = "inline-block";
        btnBT.style.opacity = "1";
        btnBT.textContent = `突破（${c.exp}/${c.exp_needed}）`;
    } else if (c.level >= 15) {
        btnBT.style.display = "none";
    } else {
        btnBT.style.display = "inline-block";
        btnBT.style.opacity = "0.5";
        btnBT.textContent = `突破（${c.exp}/${c.exp_needed}）`;
    }

    // 连接
    const connDiv = document.getElementById("connections");
    connDiv.innerHTML = "";
    loc.connections.forEach((c) => {
        const btn = document.createElement("button");
        btn.className = "conn-btn";
        btn.textContent = `前往 ${c.name}`;
        btn.onclick = () => socket.emit("move", { to: c.id });
        connDiv.appendChild(btn);
    });

    // 装备
    const eq = s.equipment;
    document.getElementById("equip-weapon").textContent = eq.weapon ? eq.weapon.name : "无";
    document.getElementById("equip-armor").textContent = eq.armor ? eq.armor.name : "无";
    document.getElementById("equip-accessory").textContent = eq.accessory ? eq.accessory.name : "无";
    document.getElementById("equip-weapon").onclick = eq.weapon ? () => socket.emit("unequip", { slot: "weapon" }) : null;
    document.getElementById("equip-armor").onclick = eq.armor ? () => socket.emit("unequip", { slot: "armor" }) : null;
    document.getElementById("equip-accessory").onclick = eq.accessory ? () => socket.emit("unequip", { slot: "accessory" }) : null;

    renderInventory(s.inventory);
    document.getElementById("online-count").textContent = `道友在线: ${s.online_count}`;
}

function renderInventory(items) {
    const div = document.getElementById("inventory-list");
    div.innerHTML = "";
    if (!items || items.length === 0) {
        div.innerHTML = '<div style="color:#3a4a42;font-size:12px;padding:4px;">储物袋空空如也</div>';
        return;
    }
    items.forEach((item) => {
        const entry = document.createElement("div");
        entry.className = "item-entry";
        entry.innerHTML = `<span><span class="item-name">${item.name}</span><span class="item-count">x${item.count}</span></span>`;
        entry.title = item.desc;
        entry.onclick = () => socket.emit("use_item", { item: item.id });
        div.appendChild(entry);
    });
}

// ═══════════════ 坊市 ═══════════════

function toggleShop() {
    const shopDiv = document.getElementById("shop-list");
    const invDiv = document.getElementById("inventory-list");
    if (shopDiv.style.display === "none") {
        shopDiv.style.display = "block";
        invDiv.style.display = "none";
        renderShop();
    } else {
        shopDiv.style.display = "none";
        invDiv.style.display = "block";
    }
}

function renderShop() {
    const shopItems = [
        // 丹药
        { id: "huiqi_dan",     name: "回气丹",     desc: "恢复30气血",       price: 15,  cat: "丹药" },
        { id: "huichun_dan",   name: "回春丹",     desc: "恢复80气血",       price: 40,  cat: "丹药" },
        { id: "xuming_dan",    name: "续命丹",     desc: "恢复200气血",      price: 120, cat: "丹药" },
        { id: "jiuzhuan_dan",  name: "九转还魂丹", desc: "气血完全恢复",     price: 350, cat: "丹药" },
        { id: "peiyuan_dan",   name: "培元丹",     desc: "获得50修为",       price: 60,  cat: "丹药" },
        { id: "juling_dan",    name: "聚灵丹",     desc: "获得150修为",      price: 200, cat: "丹药" },
        { id: "wudao_dan",     name: "悟道丹",     desc: "获得400修为",      price: 550, cat: "丹药" },
        { id: "pojing_dan",    name: "破境丹",     desc: "突破必定成功",     price: 500, cat: "丹药" },
        { id: "dingdan",       name: "凝神定魄丹", desc: "下次战斗伤害+30%", price: 150, cat: "丹药" },
        // 符箓
        { id: "liliang_fulu",  name: "力量符箓",   desc: "攻击+2(永久)",     price: 100, cat: "符箓" },
        { id: "liliang_fulu2", name: "高级力量符箓",desc: "攻击+5(永久)",    price: 350, cat: "符箓" },
        { id: "huti_fulu",     name: "护体符箓",   desc: "防御+2(永久)",     price: 100, cat: "符箓" },
        { id: "huti_fulu2",    name: "高级护体符箓",desc: "防御+5(永久)",    price: 350, cat: "符箓" },
        { id: "qifu_fulu",     name: "祈福符箓",   desc: "气血+30(永久)",    price: 200, cat: "符箓" },
        // 基础法宝（高阶装备需在炼器阁锻造）
        { id: "tiemu_sword",   name: "铁木剑",     desc: "凡器·下品 攻+3",   price: 30,    cat: "法宝" },
        { id: "cloth_robe",    name: "粗布道袍",   desc: "凡器 防+3",        price: 35,    cat: "法宝" },
        // 饰品（基础，高阶需锻造）
        { id: "qingyu_peidai", name: "青玉佩",     desc: "攻+2 气血+10",         price: 80,   cat: "饰品" },
        { id: "tongqian_hufu", name: "铜钱护符",   desc: "防+2 气血+10",         price: 80,   cat: "饰品" },
    ];
    const div = document.getElementById("shop-list");
    div.innerHTML = "";
    let lastCat = "";
    shopItems.forEach((item) => {
        if (item.cat !== lastCat) {
            lastCat = item.cat;
            const header = document.createElement("div");
            header.className = "shop-cat-header";
            header.textContent = `━━ ${item.cat} ━━`;
            div.appendChild(header);
        }
        const entry = document.createElement("div");
        entry.className = "item-entry";
        entry.innerHTML = `<span><span class="item-name">${item.name}</span> <span class="item-price">${item.price}灵石</span></span><span style="color:#6a8a7a;font-size:11px;">${item.desc}</span>`;
        entry.onclick = () => socket.emit("buy_item", { item: item.id });
        div.appendChild(entry);
    });
}

// ═══════════════ 功法面板 ═══════════════

function renderTechniques(data) {
    const learnedDiv = document.getElementById("tech-learned");
    learnedDiv.innerHTML = "";
    if (gameState && gameState.techniques && gameState.techniques.length > 0) {
        gameState.techniques.forEach((t) => {
            learnedDiv.innerHTML += `<div class="tech-entry learned"><span class="tech-name">${t.name}</span><span class="tech-tier">${t.tier}</span><span class="tech-status">已领悟</span></div>`;
        });
    } else {
        learnedDiv.innerHTML = '<div style="color:#3a4a42;font-size:12px;">尚未领悟任何功法</div>';
    }

    const availDiv = document.getElementById("tech-available");
    availDiv.innerHTML = "";
    if (data.available.length === 0) {
        availDiv.innerHTML = '<div style="color:#3a4a42;font-size:12px;">暂无可学功法</div>';
    }
    data.available.forEach((t) => {
        const entry = document.createElement("div");
        entry.className = "tech-entry" + (t.unlockable ? " unlockable" : " locked");
        entry.innerHTML = `<div><span class="tech-name">${t.name}</span><span class="tech-tier">${t.tier}</span></div><div class="tech-desc">${t.desc}</div><div class="tech-req">需${t.req_realm} | 消耗${t.cost}灵石</div>`;
        if (t.unlockable) {
            const btn = document.createElement("button");
            btn.className = "btn btn-sm btn-learn";
            btn.textContent = "参悟";
            btn.onclick = (e) => { e.stopPropagation(); socket.emit("learn_technique", { technique: t.id }); };
            entry.appendChild(btn);
        }
        availDiv.appendChild(entry);
    });
    document.getElementById("tech-modal").style.display = "flex";
}

// ═══════════════ 经脉面板 ═══════════════

function renderMeridians(data) {
    const body = document.getElementById("mer-body");
    body.innerHTML = "";
    data.data.forEach((m) => {
        const entry = document.createElement("div");
        let cls = "mer-entry";
        if (m.status === "opened") cls += " opened";
        else if (m.status === "unlockable") cls += " unlockable";
        else cls += " locked";
        entry.className = cls;
        const statusText = m.status === "opened" ? "已打通" : `消耗 ${m.cost} 修为`;
        entry.innerHTML = `<div><span class="mer-name">${m.name}</span><span class="mer-bonus">${m.bonus}</span></div><div class="mer-desc">${m.desc}</div><div class="mer-req">需${m.req_realm} | ${statusText}</div>`;
        if (m.status === "unlockable") {
            const btn = document.createElement("button");
            btn.className = "btn btn-sm btn-learn";
            btn.textContent = "冲击";
            btn.onclick = (e) => { e.stopPropagation(); socket.emit("open_meridian", { meridian: m.id }); };
            entry.appendChild(btn);
        }
        body.appendChild(entry);
    });
    document.getElementById("mer-modal").style.display = "flex";
}

// ═══════════════ 炼丹面板 ═══════════════

function showAlchemy() {
    const recipes = [
        { id: "huiqi_dan",   name: "回气丹",     mats: "灵草x3",                                       desc: "恢复30气血" },
        { id: "huichun_dan", name: "回春丹",     mats: "灵草x2 + 冰灵草x1",                            desc: "恢复80气血" },
        { id: "xuming_dan",  name: "续命丹",     mats: "冰灵草x2 + 火灵花x1 + 灵草x2",                 desc: "恢复200气血" },
        { id: "jiuzhuan_dan",name: "九转还魂丹", mats: "九转还魂草x2 + 龙涎草x1 + 凤血花x1 + 万灵果x2",desc: "气血完全恢复" },
        { id: "peiyuan_dan", name: "培元丹",     mats: "火灵花x2 + 灵草x1",                            desc: "获得50修为" },
        { id: "juling_dan",  name: "聚灵丹",     mats: "万灵果x1 + 火灵花x2 + 冰灵草x1",               desc: "获得150修为" },
        { id: "wudao_dan",   name: "悟道丹",     mats: "万灵果x2 + 九转还魂草x1",                      desc: "获得400修为" },
        { id: "pojing_dan",  name: "破境丹",     mats: "万灵果x3 + 冰灵草x2 + 火灵花x2",               desc: "突破必定成功" },
    ];
    const body = document.getElementById("alchemy-body");
    body.innerHTML = "";
    recipes.forEach((r) => {
        const entry = document.createElement("div");
        entry.className = "alchemy-entry";
        entry.innerHTML = `<div><span class="tech-name">${r.name}</span></div><div class="tech-desc">${r.desc}</div><div class="tech-req">材料：${r.mats}</div>`;
        const btn = document.createElement("button");
        btn.className = "btn btn-sm btn-learn";
        btn.textContent = "炼制";
        btn.onclick = () => socket.emit("refine_pill", { recipe: r.id });
        entry.appendChild(btn);
        body.appendChild(entry);
    });
    document.getElementById("alchemy-modal").style.display = "flex";
}

// ═══════════════ 面板控制 ═══════════════

// ═══════════════ 炼器面板 ═══════════════

function renderForgePanel(data) {
    const body = document.getElementById("forge-body");
    body.innerHTML = "";

    // Group by tier
    const tierNames = {1:"凡器",2:"法器·下品",3:"法器·上品",4:"灵器·下品",5:"灵器·上品",6:"仙器",7:"神器"};
    const groups = {};
    data.data.forEach((r) => {
        const tn = tierNames[r.tier] || `Tier ${r.tier}`;
        if (!groups[tn]) groups[tn] = [];
        groups[tn].push(r);
    });

    for (const [cat, recipes] of Object.entries(groups)) {
        const header = document.createElement("div");
        header.className = "forge-cat-header";
        header.textContent = `━━ ${cat} ━━`;
        body.appendChild(header);

        recipes.forEach((r) => {
            const entry = document.createElement("div");
            entry.className = "forge-entry" + (r.can_craft ? " unlockable" : " locked");
            const rateColor = r.success_rate >= 70 ? "#6abd7a" : r.success_rate >= 40 ? "#d4b870" : "#d45555";
            let matsHtml = r.ingredients.map((m) => {
                const color = m.have >= m.need ? "#6abd7a" : "#d45555";
                return `<span style="color:${color}">${m.name} ${m.have}/${m.need}</span>`;
            }).join("  ");
            entry.innerHTML = `
                <div class="forge-row1">
                    <span class="forge-name">${r.name}</span>
                    <span class="forge-desc">${r.slot_name}·随机属性</span>
                    <span class="forge-rate" style="color:${rateColor}">成功率 ${r.success_rate}%</span>
                </div>
                <div class="forge-row2">材料：${matsHtml}</div>
                <div class="forge-row3">需${r.req_realm} | 境界越高成功率越高</div>
            `;
            if (r.can_craft) {
                const btn = document.createElement("button");
                btn.className = "btn btn-sm btn-forge-action";
                btn.textContent = "锻造";
                btn.onclick = (e) => { e.stopPropagation(); socket.emit("forge_item", { recipe: r.id }); };
                entry.appendChild(btn);
            }
            body.appendChild(entry);
        });
    }
    document.getElementById("forge-modal").style.display = "flex";
}

function showPanel(name) {
    if (name === "techniques") socket.emit("get_techniques");
    else if (name === "meridians") socket.emit("get_meridians");
    else if (name === "alchemy") showAlchemy();
    else if (name === "forge") socket.emit("get_forge_recipes");
}
function closePanel(name) {
    const map = { tech: "tech-modal", mer: "mer-modal", alchemy: "alchemy-modal", forge: "forge-modal" };
    document.getElementById(map[name]).style.display = "none";
}

// ═══════════════ 操作 ═══════════════

function doFight() { socket.emit("fight"); }
function doMeditate() { socket.emit("meditate"); }
function doBreakthrough() { socket.emit("breakthrough"); }

function sendChat() {
    const input = document.getElementById("chat-input");
    const text = input.value.trim();
    if (text) { socket.emit("chat", { text: text }); input.value = ""; }
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("chat-input").addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendChat();
    });
});

function showLeaderboard() { socket.emit("get_leaderboard"); document.getElementById("lb-modal").style.display = "flex"; }
function closeLB() { document.getElementById("lb-modal").style.display = "none"; }

function renderLeaderboard(data) {
    const body = document.getElementById("lb-body");
    if (!data || data.length === 0) { body.innerHTML = '<p style="color:#6a8a7a;">暂无天骄入榜</p>'; return; }
    let html = '<table class="lb-table"><tr><th>排名</th><th>道号</th><th>境界</th><th>修为</th><th>斩妖</th></tr>';
    data.forEach((row, i) => {
        const medal = i === 0 ? "榜首" : i === 1 ? "第二" : i === 2 ? "第三" : `${i + 1}`;
        html += `<tr><td class="lb-rank">${medal}</td><td>${esc(row.name)}</td><td>${row.realm}</td><td>${row.exp}</td><td>${row.kills}</td></tr>`;
    });
    html += "</table>";
    body.innerHTML = html;
}

// ═══════════════ 日志 ═══════════════

function addLog(text, type) {
    const log = document.getElementById("game-log");
    const div = document.createElement("div");
    div.className = `log-line log-${type || "fight"}`;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function addChat(name, text) {
    const log = document.getElementById("chat-log");
    const div = document.createElement("div");
    div.className = "chat-msg";
    div.innerHTML = `<span class="name">${esc(name)}:</span> <span class="text">${esc(text)}</span>`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function esc(str) { const d = document.createElement("div"); d.textContent = str; return d.innerHTML; }
