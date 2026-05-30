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
    const lines = data.log;
    let i = 0;
    function showNext() {
        if (i >= lines.length) {
            socket.emit("get_state");
            return;
        }
        const line = lines[i];
        let type = "fight";
        if (line.startsWith("——")) type = "fight";
        else if (line.includes("斗法胜利")) type = "fight-win";
        else if (line.includes("陨落") || line.includes("不敌") || line.includes("灵力耗尽") || line.includes("灵力逆行")) type = "fight-lose";
        else if (line.includes("机缘") || line.includes("获得") || line.includes("天降")) type = "shop";
        else if (line.includes("损失") || line.includes("遗落") || line.includes("修为化为") || line.includes("付诸东流") || line.includes("烟消云散")) type = "error";
        else if (line.includes("突发")) type = "buff";
        addLog(line, type);
        i++;
        const delay = line.startsWith("——") ? 500 : line.includes("回合") ? 400 : line.includes("斗法") || line.includes("陨落") || line.includes("不敌") ? 600 : 200;
        setTimeout(showNext, delay);
    }
    showNext();
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

    // NPC
    const npcArea = document.getElementById("npc-area");
    const npcList = document.getElementById("npc-list");
    if (s.npcs && s.npcs.length > 0) {
        npcArea.style.display = "block";
        npcList.innerHTML = "";
        s.npcs.forEach(npc => {
            const div = document.createElement("div");
            div.className = "npc-entry";
            const tierColors = ["#8b949e","#7eb8da","#6abd7a","#d4b870"];
            div.innerHTML = `<span class="npc-name-btn" style="color:${tierColors[npc.goodwill_tier]}">${npc.name}</span><span class="npc-title">${npc.title}</span><span class="npc-gw">好感 ${npc.goodwill}（${npc.goodwill_tier_name}）</span>`;
            div.onclick = () => socket.emit("npc_interact", { npc_id: npc.id });
            npcList.appendChild(div);
        });
    } else {
        npcArea.style.display = "none";
    }

    // 任务追踪
    const tracker = document.getElementById("quest-tracker");
    if (s.quests && s.quests.active && s.quests.active.length > 0) {
        tracker.innerHTML = "";
        s.quests.active.forEach(q => {
            const div = document.createElement("div");
            div.className = "quest-entry";
            let progHtml = q.progress.map(p => {
                const done = p.done >= p.need;
                return `<div class="quest-prog ${done ? 'done' : ''}">${p.desc} ${p.done}/${p.need}</div>`;
            }).join("");
            div.innerHTML = `<div class="quest-name">${q.name}</div>${progHtml}<button class="btn btn-sm btn-quest-complete" onclick="socket.emit('quest_complete',{quest_id:'${q.id}'})">交付</button>`;
            tracker.appendChild(div);
        });
    } else {
        tracker.innerHTML = '<div style="color:#3a4a42;font-size:11px;">暂无任务</div>';
    }

    // 宗门
    const sectDiv = document.getElementById("sect-info");
    if (s.sect) {
        const rankColors = ["#8b949e","#7eb8da","#d4b870","#d45555"];
        sectDiv.innerHTML = `<div style="color:${rankColors[s.sect.rank]};font-weight:bold;">${s.sect.rank_name}</div><div style="font-size:11px;color:#6a8a7a;">贡献 ${s.sect.contrib} | ${s.sect.desc}</div>`;
    }
}

function renderInventory(items) {
    const div = document.getElementById("inventory-list");
    div.innerHTML = "";
    if (!items || items.length === 0) {
        div.innerHTML = '<div style="color:#3a4a42;font-size:12px;padding:4px;">储物袋空空如也</div>';
        return;
    }

    // 分类映射
    const catMap = {
        "consumable": "消耗品", "material": "材料", "equip": "装备",
        "pet_egg": "灵宠", "pet_food": "灵宠",
        "treasure_map": "藏宝图", "map_upgrade": "藏宝图",
        "technique_fragment": "功法残卷",
    };
    const catOrder = ["装备", "消耗品", "材料", "藏宝图", "灵宠", "功法残卷"];
    const groups = {};
    items.forEach(item => {
        const cat = catMap[item.type] || "其他";
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(item);
    });

    catOrder.forEach(cat => {
        const catItems = groups[cat];
        if (!catItems) return;
        const header = document.createElement("div");
        header.className = "shop-cat-header";
        header.textContent = `━━ ${cat} ━━`;
        div.appendChild(header);

        catItems.forEach((item) => {
            const entry = document.createElement("div");
            entry.className = "item-entry";
            let actionHtml = "";
            if (item.id.startsWith("map_") && item.id !== "map_compass") {
                actionHtml = `<button class="btn btn-sm btn-map-action" onclick="socket.emit('use_map',{item:'${item.id}'})">寻宝</button>`;
                const hasCompass = (gameState.inventory || []).find(i => i.id === "map_compass");
                if (hasCompass && item.id !== "map_legend") {
                    actionHtml += `<button class="btn btn-sm btn-compass-action" onclick="socket.emit('upgrade_map',{item:'${item.id}'})">罗盘升级</button>`;
                }
            }
            if (item.id.startsWith("frag_")) {
                const group = item.id.replace(/_\d+$/, "").replace("frag_", "");
                actionHtml = `<button class="btn btn-sm btn-frag-action" onclick="socket.emit('combine_fragments',{group:'${group}'})">合成功法</button>`;
            }
            entry.innerHTML = `<span><span class="item-name">${item.name}</span><span class="item-count">x${item.count}</span></span>${actionHtml}`;
            entry.title = item.desc;
            // 点击物品名显示详情
            entry.querySelector(".item-name").style.cursor = "pointer";
            entry.querySelector(".item-name").onclick = (e) => {
                e.stopPropagation();
                socket.emit("item_detail", { item: item.id });
            };
            if (!actionHtml) {
                // 消耗品点击整行使用
                if (["consumable", "pet_egg"].includes(item.type)) {
                    entry.onclick = () => socket.emit("use_item", { item: item.id });
                }
            }
            div.appendChild(entry);
        });
    });

    // "其他"分类
    if (groups["其他"]) {
        const header = document.createElement("div");
        header.className = "shop-cat-header";
        header.textContent = "━━ 其他 ━━";
        div.appendChild(header);
        groups["其他"].forEach(item => {
            const entry = document.createElement("div");
            entry.className = "item-entry";
            entry.innerHTML = `<span><span class="item-name">${item.name}</span><span class="item-count">x${item.count}</span></span>`;
            entry.title = item.desc;
            entry.querySelector(".item-name").style.cursor = "pointer";
            entry.querySelector(".item-name").onclick = (e) => {
                e.stopPropagation();
                socket.emit("item_detail", { item: item.id });
            };
            div.appendChild(entry);
        });
    }
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
        // 基础丹药
        { id: "huiqi_dan",     name: "回气丹",     desc: "恢复30气血",       price: 15,  cat: "丹药" },
        { id: "huichun_dan",   name: "回春丹",     desc: "恢复80气血",       price: 40,  cat: "丹药" },
        { id: "peiyuan_dan",   name: "培元丹",     desc: "获得50修为",       price: 60,  cat: "丹药" },
        { id: "dingdan",       name: "凝神定魄丹", desc: "下次战斗伤害+30%", price: 150, cat: "丹药" },
        // 基础符箓
        { id: "liliang_fulu",  name: "力量符箓",   desc: "攻击+2(永久)",     price: 100, cat: "符箓" },
        { id: "huti_fulu",     name: "护体符箓",   desc: "防御+2(永久)",     price: 100, cat: "符箓" },
        // 基础法宝
        { id: "tiemu_sword",   name: "铁木剑",     desc: "凡器·下品 攻+3",   price: 30,  cat: "法宝" },
        { id: "cloth_robe",    name: "粗布道袍",   desc: "凡器 防+3",        price: 35,  cat: "法宝" },
        // 基础饰品
        { id: "qingyu_peidai", name: "青玉佩",     desc: "攻+2 气血+10",     price: 80,  cat: "饰品" },
        { id: "tongqian_hufu", name: "铜钱护符",   desc: "防+2 气血+10",     price: 80,  cat: "饰品" },
        // 灵宠基础
        { id: "egg_common",    name: "灵兽蛋",     desc: "孵化普通灵宠",     price: 80,  cat: "灵宠" },
        { id: "pet_feed",      name: "灵兽饲料",   desc: "灵宠经验+10",      price: 15,  cat: "灵宠" },
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
            const pct = t.prof_pct || 0;
            const barColor = pct >= 100 ? "#8fd4a0" : pct >= 50 ? "#d4b870" : "#6a8a7a";
            learnedDiv.innerHTML += `<div class="tech-entry learned">
                <span class="tech-name">${t.name}</span><span class="tech-tier">${t.tier}</span>
                <div class="prof-bar-wrap"><div class="prof-bar" style="width:${pct}%;background:${barColor};"></div><span class="prof-text">${t.proficiency}/${t.max_proficiency}（${pct}%）</span></div>
            </div>`;
        });
    } else {
        learnedDiv.innerHTML = '<div style="color:#3a4a42;font-size:12px;">尚未领悟任何功法</div>';
    }

    const availDiv = document.getElementById("tech-available");
    availDiv.innerHTML = "";
    if (data.available.length === 0) {
        availDiv.innerHTML = '<div style="color:#3a4a42;font-size:12px;">暂无可学功法</div>';
    }

    // 按品阶分组
    const tierOrder = ["黄阶","玄阶","地阶","天阶"];
    const groups = {};
    data.available.forEach(t => {
        if (!groups[t.tier]) groups[t.tier] = [];
        groups[t.tier].push(t);
    });

    const alignColors = {"正道":"#7eb8da","魔道":"#d45555","中立":"#8b949e"};

    tierOrder.forEach(tier => {
        const items = groups[tier];
        if (!items || items.length === 0) return;
        const hdr = document.createElement("div");
        hdr.className = "forge-cat-header";
        hdr.textContent = `━━ ${tier} ━━`;
        availDiv.appendChild(hdr);

        items.forEach((t) => {
            const entry = document.createElement("div");
            entry.className = "tech-entry" + (t.can_learn ? " unlockable" : " locked");
            if (t.has_conflict) entry.classList.add("conflict");

            let tags = [];
            if (t.req_element) tags.push(`<span class="tech-tag tag-element">需${t.req_element}灵根</span>`);
            if (t.alignment !== "中立") tags.push(`<span class="tech-tag" style="color:${alignColors[t.alignment]}">${t.alignment}</span>`);
            let reqStr = `需${t.req_realm}`;
            if (t.cost_gold) reqStr += ` | ${t.cost_gold}灵石`;
            if (t.cost_items.length > 0) reqStr += ` | ${t.cost_items.map(i=>i.name+'x'+i.need).join(' ')}`;

            let lockReason = "";
            if (!t.can_learn && t.reasons.length > 0) {
                lockReason = `<div class="tech-lock">${t.reasons.join(' · ')}</div>`;
            }
            if (t.has_conflict) {
                lockReason += `<div class="tech-conflict">正魔道冲突！</div>`;
            }

            entry.innerHTML = `
                <div><span class="tech-name">${t.name}</span> ${tags.join(' ')}</div>
                <div class="tech-desc">${t.desc}</div>
                <div class="tech-req">${reqStr}</div>
                ${lockReason}
            `;
            if (t.can_learn) {
                const btn = document.createElement("button");
                btn.className = "btn btn-sm btn-learn";
                btn.textContent = "参悟";
                btn.onclick = (e) => { e.stopPropagation(); socket.emit("learn_technique", { technique: t.id }); };
                entry.appendChild(btn);
            }
            availDiv.appendChild(entry);
        });
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

// ═══════════════ 灵宠面板 ═══════════════

function renderPetPanel() {
    const body = document.getElementById("pet-body");
    body.innerHTML = "";

    if (!gameState || !gameState.pets || gameState.pets.length === 0) {
        body.innerHTML = '<div style="color:#3a4a42;font-size:13px;padding:8px;">你还没有灵宠。击杀妖兽或探索场景可获得灵兽蛋，在储物袋中点击蛋即可孵化。</div>';
        document.getElementById("pet-modal").style.display = "flex";
        return;
    }

    const rarityColors = { common: "#c8c0b0", rare: "#7eb8da", legend: "#d4b870" };
    const rarityNames = { common: "普通", rare: "稀有", legend: "传说" };
    const elementIcons = { 金: "金", 木: "木", 水: "水", 火: "火", 土: "土" };

    // 出战灵宠
    const activePet = gameState.pets.find(p => p.is_active);
    if (activePet) {
        const header = document.createElement("div");
        header.className = "forge-cat-header";
        header.textContent = "━━ 当前出战 ━━";
        body.appendChild(header);

        const entry = document.createElement("div");
        entry.className = "pet-entry active-pet";
        const rc = rarityColors[activePet.rarity];
        const elem = activePet.element ? ` [${elementIcons[activePet.element]}]` : "";
        entry.innerHTML = `
            <div class="pet-row1">
                <span class="pet-name" style="color:${rc}">${activePet.name}</span>
                <span class="pet-rarity">${rarityNames[activePet.rarity]}${elem}</span>
                <span class="pet-level">Lv.${activePet.level}</span>
            </div>
            <div class="pet-row2">气血+${Math.floor(activePet.hp*0.3)} 攻击+${Math.floor(activePet.atk*0.3)} 防御+${Math.floor(activePet.def*0.3)}</div>
            <div class="pet-row3">经验 ${activePet.exp}/${activePet.exp_needed}</div>
        `;
        const btnDiv = document.createElement("div");
        btnDiv.style.marginTop = "6px";

        // 喂养按钮
        const feedItems = (gameState.inventory || []).filter(i => i.id.startsWith("pet_feed"));
        feedItems.forEach(fi => {
            const btn = document.createElement("button");
            btn.className = "btn btn-sm btn-feed";
            btn.textContent = `喂${fi.name}(x${fi.count})`;
            btn.onclick = () => socket.emit("feed_pet", { pet_id: activePet.id, item: fi.id });
            btnDiv.appendChild(btn);
        });

        const deactivateBtn = document.createElement("button");
        deactivateBtn.className = "btn btn-sm";
        deactivateBtn.textContent = "收回";
        deactivateBtn.style.marginLeft = "8px";
        deactivateBtn.onclick = () => socket.emit("deactivate_pet");
        btnDiv.appendChild(deactivateBtn);

        entry.appendChild(btnDiv);
        body.appendChild(entry);
    }

    // 其他灵宠
    const bench = gameState.pets.filter(p => !p.is_active);
    if (bench.length > 0) {
        const header = document.createElement("div");
        header.className = "forge-cat-header";
        header.textContent = "━━ 灵宠列表 ━━";
        body.appendChild(header);

        bench.forEach(pet => {
            const entry = document.createElement("div");
            entry.className = "pet-entry";
            const rc = rarityColors[pet.rarity];
            const elem = pet.element ? ` [${elementIcons[pet.element]}]` : "";
            entry.innerHTML = `
                <div class="pet-row1">
                    <span class="pet-name" style="color:${rc}">${pet.name}</span>
                    <span class="pet-rarity">${rarityNames[pet.rarity]}${elem}</span>
                    <span class="pet-level">Lv.${pet.level}</span>
                </div>
                <div class="pet-row2">${pet.desc}</div>
                <div class="pet-row3">气血${pet.hp} 攻击${pet.atk} 防御${pet.def} | 经验 ${pet.exp}/${pet.exp_needed}</div>
            `;
            const btnDiv = document.createElement("div");
            btnDiv.style.marginTop = "6px";

            const feedItems = (gameState.inventory || []).filter(i => i.id.startsWith("pet_feed"));
            feedItems.forEach(fi => {
                const btn = document.createElement("button");
                btn.className = "btn btn-sm btn-feed";
                btn.textContent = `喂${fi.name}(x${fi.count})`;
                btn.onclick = () => socket.emit("feed_pet", { pet_id: pet.id, item: fi.id });
                btnDiv.appendChild(btn);
            });

            const activateBtn = document.createElement("button");
            activateBtn.className = "btn btn-sm btn-learn";
            activateBtn.textContent = "出战";
            activateBtn.style.marginLeft = "8px";
            activateBtn.onclick = () => socket.emit("activate_pet", { pet_id: pet.id });
            btnDiv.appendChild(activateBtn);

            entry.appendChild(btnDiv);
            body.appendChild(entry);
        });
    }

    document.getElementById("pet-modal").style.display = "flex";
}

// ═══════════════ NPC面板 ═══════════════

function renderNPCDetail(data) {
    const header = document.getElementById("npc-detail-header");
    const body = document.getElementById("npc-detail-body");
    const tierColors = ["#8b949e","#7eb8da","#6abd7a","#d4b870"];
    const tierNames = ["陌生","熟人","友好","知己"];

    header.innerHTML = `<h3>${data.name} <span style="font-size:12px;color:#6a8a7a;">${data.title}</span></h3>
        <div style="margin:8px 0;"><span style="color:${tierColors[data.goodwill_tier]}">好感度 ${data.goodwill}（${tierNames[data.goodwill_tier]}）</span></div>`;

    let html = `<div class="npc-dialog-box">${data.dialogue}</div>`;
    if (data.realm_dialogue) {
        html += `<div class="npc-dialog-box realm-dialog">${data.realm_dialogue}</div>`;
    }

    // 可接任务
    if (data.available_quests && data.available_quests.length > 0) {
        html += '<div class="npc-section"><strong>可接任务：</strong></div>';
        data.available_quests.forEach(q => {
            html += `<div class="npc-quest-entry">
                <div class="quest-name">${q.name} ${q.daily ? '<span style="color:#d4b870;font-size:10px;">日常</span>' : ''}</div>
                <div style="font-size:12px;color:#6a8a7a;">${q.desc}</div>
                ${q.accept_text ? `<div class="npc-dialog-box" style="font-size:11px;">${q.accept_text}</div>` : ''}
                <button class="btn btn-sm btn-learn" onclick="socket.emit('quest_accept',{quest_id:'${q.id}'})">接受任务</button>
            </div>`;
        });
    }

    // 赠礼
    html += `<div class="npc-section"><strong>赠礼</strong> <span style="font-size:11px;color:#6a8a7a;">（每日一次，赠予喜好的物品提升更多好感）</span></div>`;
    const inv = gameState ? gameState.inventory : [];
    if (inv.length > 0) {
        html += '<div style="display:flex;flex-wrap:wrap;gap:4px;">';
        inv.forEach(item => {
            html += `<button class="btn btn-sm btn-gift" onclick="socket.emit('npc_gift',{npc_id:'${data.id}',item:'${item.id}'})">${item.name}(${item.count})</button>`;
        });
        html += '</div>';
    } else {
        html += '<div style="color:#3a4a42;font-size:11px;">储物袋空空如也</div>';
    }

    body.innerHTML = html;
    document.getElementById("npc-modal").style.display = "flex";
}

function showPanel(name) {
    if (name === "techniques") socket.emit("get_techniques");
    else if (name === "meridians") socket.emit("get_meridians");
    else if (name === "alchemy") showAlchemy();
    else if (name === "forge") socket.emit("get_forge_recipes");
    else if (name === "pets") renderPetPanel();
}
function closePanel(name) {
    const map = { tech: "tech-modal", mer: "mer-modal", alchemy: "alchemy-modal", forge: "forge-modal", pet: "pet-modal", npc: "npc-modal", auction: "auction-modal", "item-detail": "item-detail-modal" };
    document.getElementById(map[name]).style.display = "none";
}

// ═══════════════ 拍卖行 ═══════════════

socket.on("auction_list", (data) => renderAuctionPanel(data));
socket.on("auction_update", (data) => {
    // 单条拍卖更新，刷新面板
    if (document.getElementById("auction-modal").style.display !== "none") {
        socket.emit("get_auction");
    }
});
socket.on("auction_log", (data) => addLog(data.text, data.type || "shop"));

function showAuction() {
    socket.emit("get_auction");
}

let auctionTimer = null;
function renderAuctionPanel(data) {
    const body = document.getElementById("auction-body");
    body.innerHTML = "";

    if (auctionTimer) { clearInterval(auctionTimer); auctionTimer = null; }

    // 显示下次刷新时间
    const refreshEl = document.getElementById("auction-next-refresh");
    if (data.next_refresh) {
        const left = Math.max(0, Math.floor((data.next_refresh - Date.now()) / 1000));
        const h = String(Math.floor(left / 3600)).padStart(2, "0");
        const m = String(Math.floor((left % 3600) / 60)).padStart(2, "0");
        const s = String(left % 60).padStart(2, "0");
        refreshEl.textContent = `下批宝物上架倒计时：${h}:${m}:${s}`;
    }

    if (!data.items || data.items.length === 0) {
        body.innerHTML = '<div style="color:#3a4a42;font-size:13px;padding:12px;">暂无拍品，稍后再来看看。</div>';
        document.getElementById("auction-modal").style.display = "flex";
        return;
    }

    const rarityColors = { common: "#c8c0b0", rare: "#7eb8da", epic: "#c8a0e8", legend: "#d4b870" };
    const rarityNames = { common: "凡品", rare: "稀有", epic: "珍品", legend: "传说" };

    data.items.forEach(item => {
        const div = document.createElement("div");
        div.className = "auction-entry" + (item.won ? " auction-won" : "");
        const rc = rarityColors[item.rarity] || "#c8c0b0";
        const rn = rarityNames[item.rarity] || "凡品";

        let statusHtml = "";
        if (item.player_won) {
            statusHtml = '<div class="auction-status" style="color:#8fd4a0;font-weight:bold;">你已拍得！物品已发放至背包</div>';
        } else if (item.won) {
            statusHtml = '<div class="auction-status auction-status-won">已流拍</div>';
        } else if (item.sold_to_npc) {
            statusHtml = '<div class="auction-status auction-status-npc">NPC已抢先拍下</div>';
        } else {
            const bidder = item.highest_bidder === "player" ? "你" : (item.highest_bidder === "npc" ? "金算盘" : "无人");
            statusHtml = `<div class="auction-status">当前最高：${bidder} ${item.current_price}灵石</div>`;
        }

        let timerHtml = "";
        if (!item.won && !item.sold_to_npc) {
            timerHtml = `<div class="auction-timer" data-ends="${item.ends_at}">剩余 --:--</div>`;
        }

        let btnHtml = "";
        if (!item.won && !item.sold_to_npc) {
            const minBid = item.current_price + item.min_increment;
            btnHtml = `<div class="auction-bid-row">
                <button class="btn btn-sm btn-auction-bid" onclick="socket.emit('auction_bid',{auction_id:'${item.auction_id}',amount:${minBid}})">${minBid}灵石</button>
                <button class="btn btn-sm btn-auction-bid" onclick="socket.emit('auction_bid',{auction_id:'${item.auction_id}',amount:${item.current_price + item.min_increment * 2}})">${item.current_price + item.min_increment * 2}灵石</button>
                <button class="btn btn-sm btn-auction-bid bid-high" onclick="socket.emit('auction_bid',{auction_id:'${item.auction_id}',amount:${item.current_price + item.min_increment * 5}})">${item.current_price + item.min_increment * 5}灵石</button>
            </div>`;
        }

        div.innerHTML = `
            <div class="auction-row1">
                <span class="auction-name" style="color:${rc}">${item.name}</span>
                <span class="auction-rarity" style="color:${rc}">[${rn}]</span>
            </div>
            <div class="auction-desc">${item.desc}</div>
            ${statusHtml}
            ${timerHtml}
            ${btnHtml}
        `;
        body.appendChild(div);
    });

    // 启动倒计时
    const nextRefresh = data.next_refresh || 0;
    function updateTimers() {
        const now = Date.now();
        // 拍品倒计时
        document.querySelectorAll(".auction-timer[data-ends]").forEach(el => {
            const ends = parseInt(el.dataset.ends);
            const left = Math.max(0, Math.floor((ends - now) / 1000));
            if (left <= 0) {
                el.textContent = "已结束";
                el.style.color = "#d45555";
            } else {
                const m = String(Math.floor(left / 60)).padStart(2, "0");
                const s = String(left % 60).padStart(2, "0");
                el.textContent = `剩余 ${m}:${s}`;
                el.style.color = left < 30 ? "#d45555" : left < 60 ? "#d4b870" : "#6a8a7a";
            }
        });
        // 下次刷新倒计时
        if (refreshEl && nextRefresh > 0) {
            const rLeft = Math.max(0, Math.floor((nextRefresh - now) / 1000));
            const rh = String(Math.floor(rLeft / 3600)).padStart(2, "0");
            const rm = String(Math.floor((rLeft % 3600) / 60)).padStart(2, "0");
            const rs = String(rLeft % 60).padStart(2, "0");
            refreshEl.textContent = `下批宝物上架倒计时：${rh}:${rm}:${rs}`;
        }
    }
    updateTimers();
    auctionTimer = setInterval(updateTimers, 1000);

    document.getElementById("auction-modal").style.display = "flex";
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

function timeStr() {
    const d = new Date();
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0") + ":" + String(d.getSeconds()).padStart(2, "0");
}

function addLog(text, type) {
    const log = document.getElementById("game-log");
    const div = document.createElement("div");
    div.className = `log-line log-${type || "fight"}`;
    div.innerHTML = `<span class="log-time">${timeStr()}</span> ${text}`;
    log.appendChild(div);
    requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });
}

function addChat(name, text) {
    const log = document.getElementById("chat-log");
    const div = document.createElement("div");
    div.className = "chat-msg";
    div.innerHTML = `<span class="log-time">${timeStr()}</span> <span class="name">${esc(name)}:</span> <span class="text">${esc(text)}</span>`;
    log.appendChild(div);
    requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });
}

function esc(str) { const d = document.createElement("div"); d.textContent = str; return d.innerHTML; }
