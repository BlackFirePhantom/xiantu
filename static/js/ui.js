/* ===== 仙途 — UI 渲染与面板控制 ===== */

// ═══════════════ 状态渲染 ═══════════════

function renderState(s) {
    const c = s.char;
    document.getElementById("char-name").textContent = c.name;
    document.getElementById("char-realm").textContent = c.realm;
    document.getElementById("char-exp").textContent = `${c.exp} / ${c.exp_needed}`;
    document.getElementById("char-hp").textContent = `${c.hp} / ${c.max_hp}`;
    if (c.mp !== undefined) {
        document.getElementById("char-mp").textContent = `${c.mp} / ${c.max_mp}`;
        const mpPct = c.max_mp > 0 ? (c.mp / c.max_mp * 100) : 0;
        const mpBar = document.getElementById("mp-bar");
        if (mpBar) mpBar.style.width = mpPct + "%";
    }
    document.getElementById("char-atk").textContent = c.atk;
    document.getElementById("char-def").textContent = c.def;
    document.getElementById("char-gold").textContent = c.gold + " 灵石";
    document.getElementById("char-kills").textContent = c.kills;
    document.getElementById("char-deaths").textContent = c.deaths;
    document.getElementById("char-mult").textContent = c.cultivation_mult + "x";

    const rootEl = document.getElementById("char-root");
    if (s.spirit_root) {
        rootEl.textContent = s.spirit_root.name + (s.spirit_root.element ? `（${s.spirit_root.element}）` : "");
        rootEl.title = s.spirit_root.desc;
    } else {
        rootEl.textContent = "未觉醒";
    }

    const hpPct = c.max_hp > 0 ? (c.hp / c.max_hp * 100) : 0;
    document.getElementById("hp-bar").style.width = hpPct + "%";

    const loc = s.location;
    document.getElementById("loc-name").textContent = loc.name;
    document.getElementById("loc-desc").textContent = loc.desc;
    const badge = document.getElementById("loc-badge");
    badge.textContent = loc.safe ? "安全" : "险地";
    badge.className = "badge " + (loc.safe ? "badge-safe" : "badge-danger");

    document.getElementById("btn-fight").style.display = loc.safe ? "none" : "inline-block";
    document.getElementById("btn-rest").style.display = loc.safe ? "inline-block" : "none";

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

    const connDiv = document.getElementById("connections");
    connDiv.innerHTML = "";
    loc.connections.forEach((c, idx) => {
        const btn = document.createElement("button");
        btn.className = "conn-btn";
        const isMobile = window.innerWidth <= 900;
        const prefix = isMobile ? "" : `[${idx + 1}] `;
        btn.textContent = `${prefix}前往 ${c.name}`;
        btn.onclick = () => socket.emit("move", { to: c.id });
        connDiv.appendChild(btn);
    });

    const eq = s.equipment;
    const slots = ["weapon", "armor", "accessory"];
    slots.forEach(slotType => {
        const container = document.querySelector(`.equip-slot-container[data-slot="${slotType}"]`);
        const slotEl = document.getElementById(`equip-${slotType}`);
        const item = eq[slotType];
        
        if (item) {
            slotEl.textContent = item.name;
            slotEl.classList.remove("empty");
            container.draggable = true;
            container.ondragstart = (e) => {
                e.dataTransfer.setData("text/plain", slotType);
                e.dataTransfer.setData("action", "unequip");
                window.currentDraggedAction = "unequip";
                window.currentDraggedSlot = slotType;
            };
            container.ondragend = () => {
                window.currentDraggedAction = null;
                window.currentDraggedSlot = null;
            };
            container.onclick = () => socket.emit("unequip", { slot: slotType });
        } else {
            slotEl.textContent = "无";
            slotEl.classList.add("empty");
            container.draggable = false;
            container.ondragstart = null;
            container.onclick = null;
        }
    });

    renderInventory(s.inventory);
    document.getElementById("online-count").textContent = `道友在线: ${s.online_count}`;

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

    const sectDiv = document.getElementById("sect-info");
    if (s.sect) {
        const rankColors = ["#8b949e","#7eb8da","#d4b870","#d45555"];
        sectDiv.innerHTML = `<div style="color:${rankColors[s.sect.rank]};font-weight:bold;">${s.sect.rank_name}</div><div style="font-size:11px;color:#6a8a7a;">贡献 ${s.sect.contrib} | ${s.sect.desc}</div>`;
    }
}

function createSecretRealmStat(label, value, detail) {
    const stat = document.createElement("article");
    stat.className = "secret-realm-stat";
    const statLabel = document.createElement("span");
    statLabel.className = "secret-realm-stat-label";
    statLabel.textContent = label;
    const statValue = document.createElement("strong");
    statValue.className = "secret-realm-stat-value";
    statValue.textContent = value;
    const statDetail = document.createElement("small");
    statDetail.textContent = detail;
    stat.append(statLabel, statValue, statDetail);
    return stat;
}

function createSecretRealmHealthCard({ role, label, name, current, max, variant, icon }) {
    const percent = max ? Math.max(0, Math.round(current / max * 100)) : 0;
    const card = document.createElement("article");
    card.className = `secret-realm-combatant ${variant}`;
    const identity = document.createElement("div");
    identity.className = "secret-realm-combatant-identity";
    const emblem = document.createElement("div");
    emblem.className = "secret-realm-combatant-emblem";
    emblem.textContent = icon;
    const copy = document.createElement("div");
    const roleText = document.createElement("span");
    roleText.className = "secret-realm-combatant-role";
    roleText.textContent = role;
    const title = document.createElement("h5");
    title.textContent = name;
    copy.append(roleText, title);
    identity.append(emblem, copy);

    const labels = document.createElement("div");
    labels.className = "secret-realm-health-labels";
    const labelText = document.createElement("span");
    labelText.textContent = label;
    const value = document.createElement("strong");
    value.textContent = `${current} / ${max}`;
    labels.append(labelText, value);
    const track = document.createElement("div");
    track.className = "secret-realm-health-track";
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-label", `${name}${label}`);
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", String(max));
    track.setAttribute("aria-valuenow", String(current));
    const fill = document.createElement("div");
    fill.className = "secret-realm-health-fill";
    fill.style.width = `${percent}%`;
    track.appendChild(fill);
    const status = document.createElement("div");
    status.className = "secret-realm-combatant-status";
    status.textContent = `${percent}% 气血 · ${current <= 0 ? "已陨落" : "仍可出战"}`;
    card.append(identity, labels, track, status);
    return card;
}

function createSecretRealmManaBar(player) {
    const wrap = document.createElement("div");
    wrap.className = "secret-realm-mana";
    const labels = document.createElement("div");
    labels.className = "secret-realm-health-labels";
    const label = document.createElement("span");
    label.textContent = "灵力 / MP";
    const value = document.createElement("strong");
    value.textContent = `${player.mp ?? 0} / ${player.max_mp ?? 0}`;
    labels.append(label, value);
    const track = document.createElement("div");
    track.className = "secret-realm-mana-track";
    const fill = document.createElement("div");
    fill.className = "secret-realm-mana-fill";
    fill.style.width = `${player.max_mp ? Math.max(0, Math.round((player.mp || 0) / player.max_mp * 100)) : 0}%`;
    track.appendChild(fill);
    wrap.append(labels, track);
    return wrap;
}

function createSecretRealmSkillPanel(data, player, disabled) {
    const panel = document.createElement("section");
    panel.className = "secret-realm-skill-panel";
    const heading = document.createElement("div");
    heading.className = "secret-realm-section-heading";
    const title = document.createElement("h4");
    title.textContent = "斩妖灵技";
    const caption = document.createElement("span");
    caption.textContent = `${data.skills?.length || 0} 项已装备技能`;
    heading.append(title, caption);
    panel.appendChild(heading);
    const skills = document.createElement("div");
    skills.className = "secret-realm-skill-grid";
    (data.skills || []).forEach(skill => {
        const cost = Number(skill.skill?.mp_cost || 0);
        const button = document.createElement("button");
        button.className = "secret-realm-skill";
        button.type = "button";
        button.disabled = disabled || (player.mp || 0) < cost;
        button.onclick = () => challengeSecretRealm("skill", skill.tech_id);
        const name = document.createElement("strong");
        name.textContent = skill.skill?.name || skill.name || skill.tech_id;
        const meta = document.createElement("span");
        meta.textContent = `${cost} MP · ${skill.skill?.desc || "消耗灵力施展"}`;
        button.append(name, meta);
        skills.appendChild(button);
    });
    if (!skills.children.length) {
        const empty = document.createElement("p");
        empty.className = "secret-realm-skill-empty";
        empty.textContent = "尚未掌握可用灵技，先用普通攻击积累战果。";
        skills.appendChild(empty);
    }
    panel.appendChild(skills);
    return panel;
}

function createSecretRealmTeamPanel(data) {
    const panel = document.createElement("section");
    panel.className = "secret-realm-team-panel";
    const heading = document.createElement("div");
    heading.className = "secret-realm-section-heading";
    const title = document.createElement("h4");
    title.textContent = data.team ? "秘境队伍" : "集结道友";
    const caption = document.createElement("span");
    caption.textContent = data.team ? `${data.team.members.length}/${data.team.max_members} 位修士` : "单人即可开战";
    heading.append(title, caption);
    panel.appendChild(heading);
    if (data.team) {
        const code = document.createElement("div");
        code.className = "secret-realm-team-code-display";
        code.textContent = `队伍码 ${data.team.id}`;
        panel.appendChild(code);
        const members = document.createElement("div");
        members.className = "secret-realm-team-members";
        data.team.members.forEach(member => {
            const item = document.createElement("div");
            item.className = "secret-realm-team-member";
            const dot = document.createElement("span");
            dot.className = "secret-realm-team-member-dot";
            const name = document.createElement("span");
            name.textContent = member.name;
            const role = document.createElement("small");
            role.textContent = member.id === data.team.leader_id ? "队长" : "队员";
            item.append(dot, name, role);
            members.appendChild(item);
        });
        panel.appendChild(members);
        const leaveButton = document.createElement("button");
        leaveButton.className = "btn btn-sm secret-realm-team-leave";
        leaveButton.textContent = "离开队伍";
        leaveButton.onclick = leaveSecretRealmTeam;
        panel.appendChild(leaveButton);
    } else {
        const hint = document.createElement("p");
        hint.className = "secret-realm-team-empty";
        hint.textContent = "创建队伍后会立即进入战场，也可以把队伍码发给道友。";
        const controls = document.createElement("div");
        controls.className = "secret-realm-team-controls";
        const soloButton = document.createElement("button");
        soloButton.className = "btn btn-sm btn-fight";
        soloButton.textContent = "单人开战";
        soloButton.onclick = createSecretRealmTeam;
        const codeInput = document.createElement("input");
        codeInput.id = "secret-realm-team-code";
        codeInput.className = "secret-realm-team-code";
        codeInput.placeholder = "队伍码";
        codeInput.maxLength = 6;
        codeInput.setAttribute("aria-label", "输入秘境队伍码");
        const joinButton = document.createElement("button");
        joinButton.className = "btn btn-sm";
        joinButton.textContent = "加入";
        joinButton.onclick = joinSecretRealmTeam;
        controls.append(soloButton, codeInput, joinButton);
        panel.append(hint, controls);
    }
    return panel;
}

function renderSecretRealm(data) {
    const body = document.getElementById("secret-realm-body");
    body.replaceChildren();
    const boss = data.boss || {};
    const player = data.player || { hp: 0, max_hp: 0, mp: 0, max_mp: 0 };
    const entriesRemaining = data.entries_remaining ?? 0;
    const isDefeated = boss.hp <= 0;

    const shell = document.createElement("section");
    shell.className = "secret-realm-shell";
    const hero = document.createElement("header");
    hero.className = "secret-realm-hero";
    const emblem = document.createElement("div");
    emblem.className = "secret-realm-hero-emblem";
    emblem.textContent = isDefeated ? "寂" : "焰";
    const heroCopy = document.createElement("div");
    const eyebrow = document.createElement("p");
    eyebrow.className = "secret-realm-eyebrow";
    eyebrow.textContent = `${data.week_id} · 本周轮换首领`;
    const name = document.createElement("h4");
    name.className = "secret-realm-boss-name";
    name.textContent = boss.name || data.name;
    const description = document.createElement("p");
    description.className = "secret-realm-boss-description";
    description.textContent = boss.description || "秘境深处，首领正在等待挑战。";
    const badges = document.createElement("div");
    badges.className = "secret-realm-badges";
    [
        `首领攻击 ${boss.attack ?? "未知"}`,
        isDefeated ? "本周已镇压" : "持续反击",
    ].forEach(text => {
        const badge = document.createElement("span");
        badge.textContent = text;
        badges.appendChild(badge);
    });
    heroCopy.append(eyebrow, name, description, badges);
    hero.append(emblem, heroCopy);
    shell.appendChild(hero);

    const stats = document.createElement("div");
    stats.className = "secret-realm-stats";
    stats.append(
        createSecretRealmStat("剩余入场", `${entriesRemaining} / 3`, "死亡或击杀后扣除"),
        createSecretRealmStat("个人战功", String(data.contribution || 0), "本周累计贡献"),
        createSecretRealmStat("造成伤害", String(data.boss_damage || 0), "对首领累计伤害"),
    );
    shell.appendChild(stats);
    shell.appendChild(createSecretRealmTeamPanel(data));

    const battlefield = document.createElement("section");
    battlefield.className = "secret-realm-battlefield";
    battlefield.append(
        createSecretRealmHealthCard({ role: "秘境首领", label: "首领气血", name: boss.name || data.name, current: boss.hp || 0, max: boss.max_hp || 0, variant: "boss", icon: "焰" }),
        Object.assign(document.createElement("div"), { className: "secret-realm-versus", textContent: "VS" }),
        createSecretRealmHealthCard({ role: "你的修士", label: "自身气血", name: "当前状态", current: player.hp, max: player.max_hp, variant: "player", icon: "剑" }),
    );
    shell.appendChild(battlefield);

    const manaPanel = document.createElement("section");
    manaPanel.className = "secret-realm-resource-panel";
    manaPanel.appendChild(createSecretRealmManaBar(player));
    shell.appendChild(manaPanel);

    // 秘境支持单人直接开战；服务端会在首次出击时自动创建队伍。
    // 因此没有队伍时不能禁用行动按钮，否则“单人即可开战”的后端能力永远触发不了。
    const actionDisabled = entriesRemaining <= 0 || isDefeated || player.hp <= 0 || secretRealmChallengePending;
    shell.appendChild(createSecretRealmSkillPanel(data, player, actionDisabled));

    const defend = document.createElement("button");
    defend.className = "btn secret-realm-defend";
    defend.type = "button";
    defend.textContent = "结阵防御 · 恢复气血并减免反击";
    defend.disabled = actionDisabled;
    defend.onclick = () => challengeSecretRealm("defend");
    shell.appendChild(defend);

    const rules = document.createElement("div");
    rules.className = "secret-realm-rule-note";
    rules.textContent = isDefeated ? "首领已伏诛，秘境将在下周轮换。" : "每次出击都会承受反击；战斗中不限出击次数，死亡或击杀首领才消耗入场次数。";
    shell.appendChild(rules);

    const action = document.createElement("button");
    action.id = "secret-realm-challenge-button";
    action.className = "btn secret-realm-challenge";
    action.textContent = isDefeated ? "本周首领已伏诛" : "出击 · 继续鏖战";
    action.disabled = actionDisabled;
    action.onclick = () => challengeSecretRealm("attack");
    shell.appendChild(action);
    body.appendChild(shell);

    const season = document.createElement("section");
    season.className = "secret-realm-affix";
    const seasonLabel = document.createElement("span");
    seasonLabel.textContent = "本周词缀";
    const seasonText = document.createElement("strong");
    seasonText.textContent = data.season ? `${data.season.name} · ${data.season.description}` : "暂无词缀";
    season.append(seasonLabel, seasonText);
    body.appendChild(season);

    const leaderboard = document.createElement("section");
    leaderboard.className = "secret-realm-leaderboard";
    const leaderboardHeading = document.createElement("div");
    leaderboardHeading.className = "secret-realm-section-heading";
    const leaderboardTitle = document.createElement("h4");
    leaderboardTitle.textContent = "本周贡献榜";
    const leaderboardCaption = document.createElement("span");
    leaderboardCaption.textContent = "按贡献排序";
    leaderboardHeading.append(leaderboardTitle, leaderboardCaption);
    leaderboard.appendChild(leaderboardHeading);
    const entries = data.leaderboard || [];
    if (entries.length) {
        entries.forEach((entry, index) => {
            const row = document.createElement("div");
            row.className = "secret-realm-rank-row";
            const rank = document.createElement("span");
            rank.className = "secret-realm-rank";
            rank.textContent = index < 3 ? ["壹", "贰", "叁"][index] : String(index + 1);
            const playerName = document.createElement("span");
            playerName.className = "secret-realm-rank-name";
            playerName.textContent = entry.name;
            const damage = document.createElement("strong");
            damage.className = "secret-realm-rank-damage";
            damage.textContent = `贡献 ${entry.contribution} · 伤害 ${entry.boss_damage}`;
            row.append(rank, playerName, damage);
            leaderboard.appendChild(row);
        });
    } else {
        const empty = document.createElement("p");
        empty.className = "secret-realm-empty";
        empty.textContent = "尚无人踏入秘境，你将成为第一位挑战者。";
        leaderboard.appendChild(empty);
    }
    body.appendChild(leaderboard);

    const settlements = data.pending_settlements || [];
    if (settlements.length) {
        const settlement = document.createElement("section");
        settlement.className = "secret-realm-settlement";
        const settlementTitle = document.createElement("h4");
        settlementTitle.textContent = "待领取周结算";
        settlement.appendChild(settlementTitle);
        settlements.forEach(item => {
            const button = document.createElement("button");
            button.className = "btn btn-sm";
            button.textContent = `${item.week_id} · 贡献 ${item.contribution} · 领取奖励`;
            button.onclick = () => claimSecretRealmSettlement(item.week_id);
            settlement.appendChild(button);
        });
        body.appendChild(settlement);
    }

    if ((data.titles || []).length) {
        const titles = document.createElement("p");
        titles.className = "secret-realm-titles";
        titles.textContent = `已获限定称号 · ${data.titles.join("、")}`;
        body.appendChild(titles);
    }
}

// ═══════════════ 背包渲染 ═══════════════

function renderSectBoss(data) {
    const body = document.getElementById("sect-boss-body");
    body.replaceChildren();
    const boss = data.boss;
    const hpPct = boss.max_hp ? Math.max(0, Math.round(boss.hp / boss.max_hp * 100)) : 0;
    const isDefeated = boss.hp <= 0;

    const arena = document.createElement("section");
    arena.className = "sect-boss-arena";

    const hero = document.createElement("div");
    hero.className = "sect-boss-hero";
    const emblem = document.createElement("div");
    emblem.className = "sect-boss-emblem";
    emblem.textContent = "蛟";
    hero.appendChild(emblem);
    const heading = document.createElement("div");
    const eyebrow = document.createElement("p");
    eyebrow.className = "sect-boss-eyebrow";
    eyebrow.textContent = `${data.week_id} · 全服护宗战`;
    const name = document.createElement("h4");
    name.className = "sect-boss-name";
    name.textContent = data.name;
    const subtitle = document.createElement("p");
    subtitle.className = "sect-boss-subtitle";
    subtitle.textContent = isDefeated ? "本周魔蛟已伏诛，同门威名远扬。" : "集结同门，以剑镇压来犯魔蛟。";
    heading.append(eyebrow, name, subtitle);
    hero.appendChild(heading);
    arena.appendChild(hero);

    const health = document.createElement("div");
    health.className = "sect-boss-health";
    const healthLabels = document.createElement("div");
    healthLabels.className = "sect-boss-health-labels";
    const healthLabel = document.createElement("span");
    healthLabel.textContent = "护宗魔蛟气血";
    const healthValue = document.createElement("strong");
    healthValue.textContent = `${boss.hp} / ${boss.max_hp}`;
    healthLabels.append(healthLabel, healthValue);
    const track = document.createElement("div");
    track.className = "sect-boss-health-track";
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-label", "护宗魔蛟剩余气血");
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", String(boss.max_hp));
    track.setAttribute("aria-valuenow", String(boss.hp));
    const fill = document.createElement("div");
    fill.className = "sect-boss-health-fill";
    fill.style.width = `${hpPct}%`;
    track.appendChild(fill);
    const status = document.createElement("div");
    status.className = "sect-boss-status";
    status.textContent = isDefeated ? "已镇压" : `尚余 ${hpPct}% 气血`;
    health.append(healthLabels, track, status);
    arena.appendChild(health);

    const rewards = document.createElement("div");
    rewards.className = "sect-boss-reward";
    rewards.textContent = "终结奖励 · 宗门令牌 ×1";
    arena.appendChild(rewards);

    const challenge = document.createElement("button");
    challenge.className = "btn sect-boss-challenge";
    challenge.textContent = isDefeated ? "本周已镇压" : "出战镇压魔蛟";
    challenge.disabled = isDefeated;
    challenge.onclick = challengeSectBoss;
    arena.appendChild(challenge);
    body.appendChild(arena);

    const leaderboard = document.createElement("section");
    leaderboard.className = "sect-boss-leaderboard";
    const title = document.createElement("h4");
    title.textContent = "护宗战功榜";
    leaderboard.appendChild(title);
    const entries = data.leaderboard || [];
    if (entries.length) {
        entries.forEach((entry, index) => {
            const row = document.createElement("div");
            row.className = "sect-boss-rank-row";
            const rank = document.createElement("span");
            rank.className = "sect-boss-rank";
            rank.textContent = index < 3 ? ["壹", "贰", "叁"][index] : String(index + 1);
            const player = document.createElement("span");
            player.className = "sect-boss-player";
            player.textContent = entry.name;
            const damage = document.createElement("strong");
            damage.className = "sect-boss-damage";
            damage.textContent = `${entry.damage} 战功`;
            row.append(rank, player, damage);
            leaderboard.appendChild(row);
        });
    } else {
        const empty = document.createElement("p");
        empty.className = "sect-boss-empty";
        empty.textContent = "尚无同门出战。你将成为今日的第一位护宗者。";
        leaderboard.appendChild(empty);
    }
    body.appendChild(leaderboard);
}

function renderInventory(items) {
    const div = document.getElementById("inventory-list");
    div.innerHTML = "";
    if (!items || items.length === 0) {
        div.innerHTML = '<div style="color:#3a4a42;font-size:12px;padding:4px;">储物袋空空如也</div>';
        return;
    }

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
            entry.querySelector(".item-name").style.cursor = "pointer";
            entry.querySelector(".item-name").onclick = (e) => {
                e.stopPropagation();
                socket.emit("item_detail", { item: item.id });
            };
            if (!actionHtml) {
                if (["consumable", "pet_egg", "equip"].includes(item.type)) {
                    entry.onclick = () => socket.emit("use_item", { item: item.id });
                }
            }
            if (item.type === "equip") {
                entry.draggable = true;
                entry.ondragstart = (e) => {
                    e.dataTransfer.setData("text/plain", item.id);
                    e.dataTransfer.setData("slot", item.slot || "");
                    e.dataTransfer.setData("action", "equip");
                    window.currentDraggedAction = "equip";
                    window.currentDraggedSlot = item.slot || "";
                    entry.classList.add("dragging");
                };
                entry.ondragend = () => {
                    window.currentDraggedAction = null;
                    window.currentDraggedSlot = null;
                    entry.classList.remove("dragging");
                };
            }
            div.appendChild(entry);
        });
    });

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
        { id: "huiqi_dan",     name: "回气丹",     desc: "恢复30气血",       price: 15,  cat: "丹药" },
        { id: "huixi_dan",     name: "回灵丹",     desc: "恢复30灵力",       price: 25,  cat: "丹药" },
        { id: "huichun_dan",   name: "回春丹",     desc: "恢复80气血",       price: 40,  cat: "丹药" },
        { id: "peiyuan_dan",   name: "培元丹",     desc: "获得50修为",       price: 60,  cat: "丹药" },
        { id: "dingdan",       name: "凝神定魄丹", desc: "下次战斗伤害+30%", price: 150, cat: "丹药" },
        { id: "liliang_fulu",  name: "力量符箓",   desc: "攻击+2(永久)",     price: 100, cat: "符箓" },
        { id: "huti_fulu",     name: "护体符箓",   desc: "防御+2(永久)",     price: 100, cat: "符箓" },
        { id: "tiemu_sword",   name: "铁木剑",     desc: "凡器·下品 攻+3",   price: 30,  cat: "法宝" },
        { id: "cloth_robe",    name: "粗布道袍",   desc: "凡器 防+3",        price: 35,  cat: "法宝" },
        { id: "qingyu_peidai", name: "青玉佩",     desc: "攻+2 气血+10",     price: 80,  cat: "饰品" },
        { id: "tongqian_hufu", name: "铜钱护符",   desc: "防+2 气血+10",     price: 80,  cat: "饰品" },
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

// ═══════════════ 炼器面板 ═══════════════

function renderForgePanel(data) {
    const body = document.getElementById("forge-body");
    body.innerHTML = "";

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

// ═══════════════ 拍卖行 ═══════════════

function showAuction() {
    socket.emit("get_auction");
}

let auctionTimer = null;
function renderAuctionPanel(data) {
    const body = document.getElementById("auction-body");
    body.innerHTML = "";

    if (auctionTimer) { clearInterval(auctionTimer); auctionTimer = null; }

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

    const nextRefresh = data.next_refresh || 0;
    function updateTimers() {
        const now = Date.now();
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

// ═══════════════ 面板控制 ═══════════════

function showPanel(name) {
    if (name === "techniques") socket.emit("get_techniques");
    else if (name === "meridians") socket.emit("get_meridians");
    else if (name === "alchemy") showAlchemy();
    else if (name === "forge") socket.emit("get_forge_recipes");
    else if (name === "pets") renderPetPanel();
}

const MODAL_MAP = {
    tech: "tech-modal", mer: "mer-modal", alchemy: "alchemy-modal",
    forge: "forge-modal", pet: "pet-modal", npc: "npc-modal",
    auction: "auction-modal", "item-detail": "item-detail-modal",
    lb: "lb-modal",
};

function closePanel(name) {
    const id = MODAL_MAP[name];
    if (id) document.getElementById(id).style.display = "none";
}

function closeAllModals() {
    Object.values(MODAL_MAP).forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
    });
    const fortune = document.getElementById("fortune-popup");
    if (fortune) fortune.style.display = "none";
}

function isAnyModalOpen() {
    return Object.values(MODAL_MAP).some(id => {
        const el = document.getElementById(id);
        return el && el.style.display !== "none";
    });
}

// ═══════════════ 天骄榜 ═══════════════

function showLeaderboard() {
    socket.emit("get_leaderboard");
    document.getElementById("lb-modal").style.display = "flex";
}

function closeLB() {
    document.getElementById("lb-modal").style.display = "none";
}

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

// ═══════════════ 日志工具 ═══════════════

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

function initDragAndDrop() {
    // 1. 设置装备槽为拖放目标（穿戴装备）
    document.querySelectorAll(".equip-slot-container").forEach(container => {
        const slotType = container.getAttribute("data-slot");
        
        container.addEventListener("dragover", (e) => {
            if (window.currentDraggedAction === "equip" && window.currentDraggedSlot === slotType) {
                e.preventDefault();
                container.classList.add("drag-active");
            }
        });
        
        container.addEventListener("dragleave", () => {
            container.classList.remove("drag-active");
        });
        
        container.addEventListener("drop", (e) => {
            e.preventDefault();
            container.classList.remove("drag-active");
            const itemId = e.dataTransfer.getData("text/plain");
            const action = e.dataTransfer.getData("action");
            const slot = e.dataTransfer.getData("slot");
            if (action === "equip" && slot === slotType) {
                socket.emit("use_item", { item: itemId });
            }
        });
    });

    // 2. 设置储物袋区域为拖放目标（卸下装备）
    const invList = document.getElementById("inventory-list");
    invList.addEventListener("dragover", (e) => {
        if (window.currentDraggedAction === "unequip") {
            e.preventDefault();
            invList.classList.add("drag-active");
        }
    });

    invList.addEventListener("dragleave", () => {
        invList.classList.remove("drag-active");
    });

    invList.addEventListener("drop", (e) => {
        e.preventDefault();
        invList.classList.remove("drag-active");
        const slot = e.dataTransfer.getData("text/plain");
        const action = e.dataTransfer.getData("action");
        if (action === "unequip") {
            socket.emit("unequip", { slot: slot });
        }
    });
}

function switchMobileTab(tab) {
    const layout = document.querySelector(".game-layout");
    if (!layout) return;
    
    // 切换状态类名
    layout.className = `game-layout active-tab-${tab}`;
    
    // 高亮底部按钮
    document.querySelectorAll(".mobile-tabs .tab-btn").forEach(btn => {
        btn.classList.remove("active");
    });
    
    const tabsMap = {
        "game": 0,
        "player": 1,
        "social": 2
    };
    const activeBtn = document.querySelectorAll(".mobile-tabs .tab-btn")[tabsMap[tab]];
    if (activeBtn) {
        activeBtn.classList.add("active");
    }
}

// ═══════════════ 回合制战斗面板 ═══════════════

let combatState = null;

function showCombatPanel(data) {
    combatState = data;
    document.getElementById("action-bar").style.display = "none";
    document.getElementById("fortune-popup").style.display = "none";
    const panel = document.getElementById("combat-panel");
    panel.style.display = "block";

    // 怪物完整信息
    const m = data.monster;
    document.getElementById("combat-monster-name").textContent = m.name;
    document.getElementById("combat-monster-realm").textContent = m.realm || `(${m.level}级)`;
    document.getElementById("combat-monster-element").textContent = m.element ? `${m.element}属性` : "";
    document.getElementById("combat-monster-atk").textContent = m.atk;
    document.getElementById("combat-monster-def").textContent = m.def;
    const skillNames = (m.skills || []).map(s => s.name).join("、");
    document.getElementById("combat-monster-skills").textContent = skillNames || "无";

    // 初始日志
    const logDiv = document.getElementById("combat-log");
    logDiv.innerHTML = "";
    data.log.forEach(line => addCombatLogLine(logDiv, line));

    // 强制不带动画初始化 HP/Hurt 宽度，防止残影
    const mhBar = document.getElementById("combat-monster-hp-bar");
    const mhHurt = document.getElementById("combat-monster-hp-hurt");
    const phBar = document.getElementById("combat-player-hp-bar");
    const phHurt = document.getElementById("combat-player-hp-hurt");
    if (mhBar) mhBar.style.transition = 'none';
    if (mhHurt) mhHurt.style.transition = 'none';
    if (phBar) phBar.style.transition = 'none';
    if (phHurt) phHurt.style.transition = 'none';

    updateCombatHP(data);

    // 强制重绘以应用初始值
    if (mhBar) mhBar.offsetHeight;

    // 恢复过渡动画
    if (mhBar) mhBar.style.transition = '';
    if (mhHurt) mhHurt.style.transition = '';
    if (phBar) phBar.style.transition = '';
    if (phHurt) phHurt.style.transition = '';

    renderCombatActions(data);
}

function updateCombatRound(data) {
    if (!combatState) return;
    const logDiv = document.getElementById("combat-log");
    data.log.forEach(line => addCombatLogLine(logDiv, line));
    logDiv.scrollTop = logDiv.scrollHeight;

    combatState.player_hp = data.player_hp;
    combatState.player_max_hp = data.player_max_hp;
    combatState.player_mp = data.player_mp;
    combatState.player_max_mp = data.player_max_mp;
    combatState.monster_hp = data.monster_hp;
    combatState.monster_max_hp = data.monster_max_hp;
    combatState.skills = data.skills;
    combatState.round = data.round;

    updateCombatHP(data);

    // 显示buff/debuff
    let buffsText = "";
    if (data.player_buffs) {
        for (const [stat, info] of Object.entries(data.player_buffs)) {
            const pct = Math.round((info.mult - 1) * 100);
            buffsText += `${stat === "atk" ? "攻击" : "防御"}${pct >= 0 ? "+" : ""}${pct}%(${info.rounds}回合) `;
        }
    }
    if (data.player_debuffs) {
        for (const [stat, info] of Object.entries(data.player_debuffs)) {
            const pct = Math.round((info.mult - 1) * 100);
            buffsText += `${stat === "atk" ? "攻击" : "防御"}${pct}%(${info.rounds}回合) `;
        }
    }
    document.getElementById("combat-buffs").textContent = buffsText;

    renderCombatActions(data);
}

function endCombat(data) {
    const logDiv = document.getElementById("combat-log");
    data.log.forEach(line => {
        if (line.includes("斗法胜利") || line.includes("天降机缘")) {
            addCombatLogLine(logDiv, line, "fight-win");
        } else if (line.includes("陨落") || line.includes("不敌") || line.includes("损失")) {
            addCombatLogLine(logDiv, line, "fight-lose");
        } else {
            addCombatLogLine(logDiv, line);
        }
    });
    logDiv.scrollTop = logDiv.scrollHeight;

    // 也写到主日志
    data.log.forEach(line => {
        let type = "info";
        if (line.includes("斗法胜利")) type = "fight-win";
        else if (line.includes("陨落") || line.includes("不敌")) type = "fight-lose";
        else if (line.includes("机缘") || line.includes("获得")) type = "shop";
        addLog(line, type);
    });

    // 延迟隐藏战斗面板
    setTimeout(() => {
        document.getElementById("combat-panel").style.display = "none";
        document.getElementById("action-bar").style.display = "flex";
        combatState = null;
        socket.emit("get_state");
    }, 2000);
}

function updateCombatHP(data) {
    const mhpPct = data.monster_max_hp > 0 ? (data.monster_hp / data.monster_max_hp * 100) : 0;
    document.getElementById("combat-monster-hp-bar").style.width = Math.max(0, mhpPct) + "%";
    const mhHurt = document.getElementById("combat-monster-hp-hurt");
    if (mhHurt) mhHurt.style.width = Math.max(0, mhpPct) + "%";
    document.getElementById("combat-monster-hp-text").textContent = `${Math.max(0, data.monster_hp)} / ${data.monster_max_hp}`;

    const phpPct = data.player_max_hp > 0 ? (data.player_hp / data.player_max_hp * 100) : 0;
    document.getElementById("combat-player-hp-bar").style.width = Math.max(0, phpPct) + "%";
    const phHurt = document.getElementById("combat-player-hp-hurt");
    if (phHurt) phHurt.style.width = Math.max(0, phpPct) + "%";
    document.getElementById("combat-player-hp-text").textContent = `${Math.max(0, data.player_hp)} / ${data.player_max_hp}`;

    const mpPct = data.player_max_mp > 0 ? (data.player_mp / data.player_max_mp * 100) : 0;
    document.getElementById("combat-player-mp-bar").style.width = Math.max(0, mpPct) + "%";
    document.getElementById("combat-player-mp-text").textContent = `${data.player_mp} / ${data.player_max_mp}`;
}

function renderCombatActions(data) {
    const actionsDiv = document.getElementById("combat-actions");
    actionsDiv.innerHTML = "";

    // 普攻按钮
    const atkBtn = document.createElement("button");
    atkBtn.className = "btn btn-fight";
    atkBtn.textContent = "普攻";
    atkBtn.onclick = () => { sendFightAction("attack"); };
    actionsDiv.appendChild(atkBtn);

    // 技能按钮
    if (data.skills) {
        data.skills.forEach((s, i) => {
            const skill = s.skill;
            const btn = document.createElement("button");
            btn.className = "btn btn-skill";
            const mpCost = skill.mp_cost || 0;
            const canUse = data.player_mp >= mpCost;
            if (!canUse) btn.disabled = true;
            btn.innerHTML = `${skill.name}<span class="mp-cost">🔪${mpCost}</span>`;
            btn.title = skill.desc || "";
            btn.onclick = () => { sendFightAction("skill", s.tech_id); };
            actionsDiv.appendChild(btn);
        });
    }

    // 防御按钮
    const defBtn = document.createElement("button");
    defBtn.className = "btn btn-rest";
    defBtn.textContent = "防御";
    defBtn.onclick = () => { sendFightAction("defend"); };
    actionsDiv.appendChild(defBtn);

    // 逃跑按钮
    const fleeBtn = document.createElement("button");
    fleeBtn.className = "btn";
    fleeBtn.textContent = "逃跑";
    fleeBtn.onclick = () => { sendFightAction("flee"); };
    actionsDiv.appendChild(fleeBtn);
}

function sendFightAction(action, skillId) {
    const data = { action: action };
    if (skillId) data.skill_id = skillId;
    socket.emit("fight_action", data);
    // 禁用按钮防止重复点击
    document.querySelectorAll("#combat-actions .btn").forEach(b => b.disabled = true);
}

function addCombatLogLine(logDiv, line, type) {
    const div = document.createElement("div");
    let cls = "combat-log-line";
    if (!type) {
        if (line.startsWith("--")) type = "fight";
        else if (line.includes("施展") || line.includes("施展")) type = "buff";
        else if (line.includes("伤害") && line.includes("你")) type = "fight-lose";
        else if (line.includes("伤害")) type = "fight";
        else type = "info";
    }
    div.className = cls + " log-" + type;
    div.textContent = line;
    logDiv.appendChild(div);
}


let arenaActiveTab = "leaderboard";
let lastArenaData = null;

function switchArenaTab(tab) {
    arenaActiveTab = tab;
    if (lastArenaData) {
        renderArena(lastArenaData);
    }
}

function renderArena(data) {
    lastArenaData = data;
    const body = document.getElementById("arena-body");
    body.innerHTML = "";

    const grid = document.createElement("div");
    grid.className = "arena-grid";

    // Column 1: Stats & Defense config
    const col1 = document.createElement("div");
    col1.className = "arena-card";
    
    let col1Html = `
        <div class="arena-card-title">我的论道战绩</div>
        <div class="arena-profile-stat">
            <div class="arena-stat-item">
                <label>论道积分</label>
                <span>${data.score}</span>
            </div>
            <div class="arena-stat-item">
                <label>剩余挑战</label>
                <span>${data.challenges_remaining} 次</span>
            </div>
            <div class="arena-stat-item">
                <label>胜场</label>
                <span>${data.wins}</span>
            </div>
            <div class="arena-stat-item">
                <label>败场</label>
                <span>${data.losses}</span>
            </div>
        </div>
        
        <div class="arena-defense-setup">
            <div class="arena-card-title" style="margin-top:15px; margin-bottom:5px;">防守套路配置</div>
            <h5 style="margin: 0 0 10px 0; color: #89979e; font-size:11px; font-weight: normal;">配置 3 个斗法释放的灵技</h5>
    `;
    
    for (let i = 1; i <= 3; i++) {
        col1Html += `
            <div class="arena-defense-slot" style="margin-bottom: 8px;">
                <span style="font-size:12px; color:#c8d7df; width: 45px;">第${i}手</span>
                <select id="arena-defense-select-${i}" class="arena-defense-select" onchange="setArenaDefense()">
                    <option value="">普通攻击</option>
                    ${data.all_skills.map(s => `
                        <option value="${s.tech_id}" ${data.defense_skills[i-1] === s.tech_id ? "selected" : ""}>${s.name}</option>
                    `).join("")}
                </select>
            </div>
        `;
    }
    col1Html += `</div>`;
    col1.innerHTML = col1Html;

    // Column 2: Opponent matching
    const col2 = document.createElement("div");
    col2.className = "arena-card";
    
    let col2Html = `<div class="arena-card-title">寻敌挑战</div><div class="arena-opponents-list">`;
    if (data.opponents.length === 0) {
        col2Html += `<div class="secret-realm-empty">修仙界暂时没有其他修士可与之论道。</div>`;
    } else {
        data.opponents.forEach(opp => {
            col2Html += `
                <div class="arena-opponent-item">
                    <div class="arena-opponent-avatar">${opp.name[0]}</div>
                    <div class="arena-opponent-info">
                        <h4>${opp.name}</h4>
                        <p style="margin: 3px 0 0 0; color: #89979e; font-size: 11px;">境界: <strong style="color: #dfc28a;">${opp.realm || "凡人"}</strong></p>
                        <p style="margin: 3px 0 0 0; color: #89979e; font-size: 11px;">论道积分: <strong style="color: #dfc28a;">${opp.arena_score}</strong></p>
                    </div>
                    <button class="btn btn-sm btn-fight" onclick="challengeArena(${opp.user_id})" ${data.challenges_remaining <= 0 ? "disabled" : ""}>挑战</button>
                </div>
            `;
        });
    }
    col2Html += `</div>`;
    col2.innerHTML = col2Html;

    // Column 3: Leaderboard / Battle Logs
    const col3 = document.createElement("div");
    col3.className = "arena-card";
    col3.style.padding = "10px";
    
    const tabHeaders = document.createElement("div");
    tabHeaders.className = "arena-rankings-logs-tabs";
    
    const rankTab = document.createElement("button");
    rankTab.className = "arena-tab-btn" + (arenaActiveTab === "leaderboard" ? " active" : "");
    rankTab.textContent = "天骄论道榜";
    rankTab.onclick = () => switchArenaTab("leaderboard");
    
    const logTab = document.createElement("button");
    logTab.className = "arena-tab-btn" + (arenaActiveTab === "logs" ? " active" : "");
    logTab.textContent = "论道记录";
    logTab.onclick = () => switchArenaTab("logs");
    
    tabHeaders.append(rankTab, logTab);
    col3.appendChild(tabHeaders);
    
    const tabContent = document.createElement("div");
    tabContent.id = "arena-tab-content";
    
    if (arenaActiveTab === "leaderboard") {
        let rankHtml = `
            <table class="lb-table" style="margin-top:5px;">
                <thead>
                    <tr>
                        <th style="padding: 6px; font-size:11px;">排名</th>
                        <th style="padding: 6px; font-size:11px;">修士</th>
                        <th style="padding: 6px; font-size:11px; text-align:right;">积分</th>
                    </tr>
                </thead>
                <tbody>
        `;
        if (data.leaderboard.length === 0) {
            rankHtml += `<tr><td colspan="3" style="text-align:center; color:#89979e; font-size:11px; padding:10px;">暂无排名</td></tr>`;
        } else {
            data.leaderboard.forEach((r, idx) => {
                rankHtml += `
                    <tr>
                        <td style="padding: 6px; font-size:12px;" class="lb-rank">#${idx + 1}</td>
                        <td style="padding: 6px; font-size:12px; color:#c8d7df;">${r.name}<br/><small style="color:#7f98a2; font-size:9px;">${r.realm || "凡人"}</small></td>
                        <td style="padding: 6px; font-size:12px; text-align:right; color:#dfc28a; font-family:monospace;">${r.arena_score}</td>
                    </tr>
                `;
            });
        }
        rankHtml += `</tbody></table>`;
        tabContent.innerHTML = rankHtml;
    } else {
        let logHtml = `<div class="arena-logs-list" style="max-height: 380px; overflow-y: auto;">`;
        if (data.logs.length === 0) {
            logHtml += `<div class="secret-realm-empty" style="border:none; padding:20px;">暂无斗法记录</div>`;
        } else {
            data.logs.forEach(l => {
                const myName = document.getElementById("char-name").textContent.trim();
                const isIWinner = l.winner_id === l.challenger_id ? (l.challenger_name === myName) : (l.defender_name === myName);
                const roleText = l.challenger_name === myName ? "挑战" : "防守";
                const oppName = l.challenger_name === myName ? l.defender_name : l.challenger_name;
                const outcomeClass = isIWinner ? "arena-log-win" : "arena-log-lose";
                const outcomeText = isIWinner ? "胜" : "败";
                
                logHtml += `
                    <div class="arena-log-item">
                        <span style="color:#89979e;">[${roleText}]</span> 对阵 <strong style="color:#cbd9de;">${oppName}</strong> 
                        <span class="${outcomeClass}" style="font-weight:bold; margin-left:4px;">${outcomeText}</span>
                        <span style="color:#dfc28a; font-family:monospace; margin-left:4px;">(${isIWinner ? "+" : "-"}${l.score_change})</span>
                        <a onclick="viewArenaLogDetail(${l.id})">回放</a>
                    </div>
                `;
            });
        }
        logHtml += `</div>`;
        tabContent.innerHTML = logHtml;
    }
    col3.appendChild(tabContent);

    grid.append(col1, col2, col3);
    body.appendChild(grid);
}

function viewArenaLogDetail(logId) {
    if (!lastArenaData || !lastArenaData.logs) return;
    const log = lastArenaData.logs.find(l => l.id === logId);
    if (!log) return;
    
    let combatLogLines = [];
    try {
        combatLogLines = JSON.parse(log.combat_log);
    } catch (e) {
        combatLogLines = [log.combat_log];
    }
    
    const body = document.getElementById("arena-combat-body");
    body.innerHTML = combatLogLines.join("\n");
    document.getElementById("arena-combat-modal").style.display = "flex";
}

function showArenaCombatResult(data) {
    let logLines = [];
    try {
        logLines = typeof data.log === "string" ? JSON.parse(data.log) : data.log;
    } catch (e) {
        logLines = [data.log];
    }
    
    const body = document.getElementById("arena-combat-body");
    body.innerHTML = logLines.join("\n");
    document.getElementById("arena-combat-modal").style.display = "flex";
    
    const isWinner = data.winner_id === lastArenaData.my_id;
    addLog(`【论道结果】你发起了挑战，战绩：${isWinner ? "【大胜】" : "【败北】"}，积分变动：${isWinner ? "+" : "-"}${data.score_change}。`, isWinner ? "success" : "error");
}
