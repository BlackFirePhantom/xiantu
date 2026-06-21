"""仙途 — 修仙文字在线游戏主程序"""

import random
import hashlib
import secrets
import time
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

from config import SECRET_KEY, CORS_ALLOWED_ORIGINS, HOST, PORT, AFK_TIMEOUT, AFK_MAX_HOURS, AFK_INTERVAL

from models import (
    init_db, create_user, get_user, create_character,
    get_character, update_character, get_character_inventory,
    set_character_inventory, get_leaderboard,
)
from game_data import (
    LOCATIONS, MONSTERS, ITEMS, DROP_TABLE, PET_EGG_MONSTER_DROPS, MAP_MONSTER_DROPS,
    LOCATION_UNIQUE_DROPS,
    TREASURE_TABLES, FRAGMENT_RECIPES, EXP_PER_LEVEL, MAX_LEVEL,
    BREAKTHROUGH_CHANCE, REALMS, SPIRIT_ROOTS, TECHNIQUES, MERIDIANS,
    ALIGNMENT_CONFLICTS, RECIPES, FORTUNE_EVENTS, SURPRISE_EVENTS, ELEMENT_COUNTER,
    FORGE_RECIPES, FORGE_REALM_BONUS_PER_LV,
    PET_SPECIES, PET_EGG_TIERS, PET_BATTLE_RATIO, PET_EXP_PER_LEVEL, PET_MAX_LEVEL,
    realm_name, spawn_monster, roll_spirit_root, generate_equip, lookup_item,
    hatch_egg, get_pet_stats, get_pet_exp_needed,
    IDLE_EXP_PER_SEC, IDLE_MAX_HOURS,
    TECHNIQUE_MAX_PROFICIENCY, TECHNIQUE_PROFICIENCY_TIERS, TECHNIQUE_MEDITATE_PROFICIENCY,
)
from npc_data import (
    NPCS, QUESTS, NPC_GOODWILL_TIERS, SECT_RANKS,
    get_goodwill_tier, get_sect_rank,
)

# game 模块
from game.utils import (
    calc_level_stats, get_full_stats, get_exp_needed, get_cultivation_mult,
    format_duration, gain_proficiency, get_proficiency, proficiency_mult,
)
from game.cultivation import process_offline_cultivation
from game.pet import get_pet_display_info, hatch_pet_egg, feed_pet
from game.npc import (
    get_npc_info_for_location, get_quest_info, get_sect_info,
    interact_with_npc, give_npc_gift, accept_quest, complete_quest,
    check_quest_progress,
)
from game.treasure import use_treasure_map, upgrade_treasure_map, combine_fragments
from game.events import check_fortune, process_surprise, process_fortune_outcome
from game.auction import (
    AUCTION_POOL, AUCTION_NPC, _item_name as auction_item_name,
    npc_may_bid, npc_do_bid,
)

app = Flask(__name__)
app.secret_key = SECRET_KEY
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins=CORS_ALLOWED_ORIGINS)

online_users = {}
last_activity = {}     # username -> timestamp of last action
afk_players = {}       # username -> timestamp when AFK started

# ═══════════════ 辅助函数（使用 game.utils） ═══════════════

def touch_activity(username):
    """记录用户活动时间"""
    last_activity[username] = time.time()
    if username in afk_players:
        del afk_players[username]
        socketio.emit("afk_status", {"afk": False}, room=online_users.get(username))

def check_afk_loop():
    """后台循环：检测挂机状态并发放挂机奖励"""
    while True:
        socketio.sleep(AFK_INTERVAL)
        now = time.time()
        for username, sid in list(online_users.items()):
            if username not in last_activity:
                continue
            idle_time = now - last_activity[username]

            # 进入挂机
            if idle_time >= AFK_TIMEOUT and username not in afk_players:
                afk_players[username] = now
                socketio.emit("afk_status", {"afk": True, "msg": "你已进入挂机修炼状态（10分钟无操作自动触发）"}, room=sid)

            # 挂机中发放奖励
            if username in afk_players:
                user = get_user(username)
                if not user:
                    continue
                char = get_character(user["id"])
                if not char:
                    continue

                loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
                afk_duration = now - afk_players[username]
                max_duration = AFK_MAX_HOURS * 3600

                if afk_duration > max_duration:
                    afk_players[username] = now - max_duration
                    afk_duration = max_duration

                if afk_duration < AFK_INTERVAL:
                    continue

                mult = get_cultivation_mult(char)
                exp_gain = int(IDLE_EXP_PER_SEC * AFK_INTERVAL * mult)

                # 挂机地点有怪物时，概率掉落材料
                drops = []
                if not loc["safe"] and random.random() < 0.3:
                    mat_pool = ["lingcao", "yaogu", "yaopimo", "hantie_kuang"]
                    drops.append(random.choice(mat_pool))

                inv = get_character_inventory(user["id"])
                for item_id in drops:
                    inv[item_id] = inv.get(item_id, 0) + 1
                set_character_inventory(user["id"], inv)

                if get_exp_needed(char["level"]) != "-":
                    update_character(user["id"], exp=char["exp"] + exp_gain)

                # 挂机中自动回血（安全区域）
                if loc["safe"]:
                    stats = get_full_stats(char)
                    if char["hp"] < stats["max_hp"]:
                        update_character(user["id"], hp=stats["max_hp"])

                emit("afk_tick", {
                    "exp": exp_gain,
                    "drops": [ITEMS[d]["name"] for d in drops],
                    "duration": format_duration(int(afk_duration)),
                }, room=sid)

def hash_password(password):
    """使用 werkzeug 生成安全密码哈希（带盐）"""
    return generate_password_hash(password)

def verify_password(password, stored_hash):
    """验证密码，兼容旧的 SHA-256 哈希"""
    if stored_hash.startswith("pbkdf2:") or stored_hash.startswith("scrypt:"):
        return check_password_hash(stored_hash, password)
    # 向后兼容：旧的 SHA-256 哈希
    if stored_hash == hashlib.sha256(password.encode()).hexdigest():
        return True
    return False

# ═══════════════ 战斗文案（使用 game.combat） ═══════════════
from game.combat import fmt_attack, fmt_monster_attack

# ═══════════════ 路由 ═══════════════

@app.route("/")
def index():
    if "user_id" in session: return redirect(url_for("game"))
    return render_template("index.html", page="login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            return render_template("index.html", page="register", error="道号和密令不可为空")
        if len(username) < 2 or len(username) > 16:
            return render_template("index.html", page="register", error="道号长度2-16个字符")
        if len(password) < 4:
            return render_template("index.html", page="register", error="密令至少4个字符")
        if create_user(username, hash_password(password)):
            logger.info("新用户注册：%s", username)
            return render_template("index.html", page="login", success="注册成功，请登录踏入仙途")
        return render_template("index.html", page="register", error="此道号已被他人所用")
    return render_template("index.html", page="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = get_user(username)
        if user and verify_password(password, user["password_hash"]):
            # 自动迁移旧的 SHA-256 密码到安全哈希
            if not (user["password_hash"].startswith("pbkdf2:") or user["password_hash"].startswith("scrypt:")):
                from models import get_db
                with get_db() as conn:
                    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                                 (hash_password(password), user["id"]))
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            logger.info("用户登录：%s", username)
            char = get_character(user["id"])
            if char:
                return redirect(url_for("game"))
            else:
                return redirect(url_for("create"))
        return render_template("index.html", page="login", error="道号或密令有误")
    return render_template("index.html", page="login")

@app.route("/logout")
def logout():
    username = session.get("username")
    if username and username in online_users: online_users.pop(username)
    session.clear()
    return redirect(url_for("index"))

@app.route("/game")
def game():
    if "user_id" not in session: return redirect(url_for("index"))
    char = get_character(session["user_id"])
    if not char: return redirect(url_for("create"))
    return render_template("game.html", username=session["username"])

@app.route("/create", methods=["GET", "POST"])
def create():
    if "user_id" not in session: return redirect(url_for("index"))
    if get_character(session["user_id"]): return redirect(url_for("game"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name or len(name) < 1 or len(name) > 12:
            return render_template("index.html", page="create", error="道号1-12个字符")
        root = roll_spirit_root()
        if create_character(session["user_id"], name, root):
            return redirect(url_for("game"))
        return render_template("index.html", page="create", error="创建失败（道号可能已存在）")
    return render_template("index.html", page="create")

# ═══════════════ WebSocket ═══════════════

@socketio.on("connect")
def handle_connect():
    if "username" not in session:
        return False
    username = session["username"]
    online_users[username] = request.sid
    touch_activity(username)
    emit("system_msg", {"text": f"{username} 踏入了修仙界"}, broadcast=True, namespace="/")

@socketio.on("disconnect")
def handle_disconnect(reason=None):
    username = session.get("username")
    if username:
        online_users.pop(username, None)
        afk_players.pop(username, None)
        last_activity.pop(username, None)
        emit("system_msg", {"text": f"{username} 离开了修仙界"}, broadcast=True, namespace="/")


@socketio.on("get_state")
def handle_get_state():
    if "user_id" not in session: return
    touch_activity(session.get("username", ""))
    char = get_character(session["user_id"])
    if not char:
        emit("need_create")
        return

    # 处理离线挂机
    gain, elapsed = process_offline_cultivation(char)
    if gain > 0:
        new_exp = char["exp"] + gain
        update_character(session["user_id"], exp=new_exp, last_active=datetime.utcnow().isoformat())
        char = get_character(session["user_id"])
        emit("game_msg", {"text": f"你闭关修炼了 {format_duration(elapsed)}，修为增长 {gain}。", "type": "heal"})
    else:
        update_character(session["user_id"], last_active=datetime.utcnow().isoformat())

    loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
    stats = get_full_stats(char)
    inv = get_character_inventory(session["user_id"])
    inv_display = []
    for item_id, count in inv.items():
        item = lookup_item(item_id)
        if item:
            inv_display.append({
                "id": item_id,
                "name": item["name"],
                "count": count,
                "desc": item.get("desc", ""),
                "type": item.get("type", "misc"),
                "slot": item.get("slot")
            })

    equip_info = {"weapon": None, "armor": None, "accessory": None}
    w = lookup_item(char["weapon"]) if char["weapon"] else None
    if w: equip_info["weapon"] = {"id": char["weapon"], "name": w["name"], "desc": w.get("desc", ""), "slot": w.get("slot", "weapon")}
    a = lookup_item(char["armor"]) if char["armor"] else None
    if a: equip_info["armor"] = {"id": char["armor"], "name": a["name"], "desc": a.get("desc", ""), "slot": a.get("slot", "armor")}
    ac = lookup_item(char["accessory"]) if char["accessory"] else None
    if ac: equip_info["accessory"] = {"id": char["accessory"], "name": ac["name"], "desc": ac.get("desc", ""), "slot": ac.get("slot", "accessory")}

    connections_display = [{"id": c, "name": LOCATIONS[c]["name"]} for c in loc["connections"] if c in LOCATIONS]

    # 灵根信息
    sr_id = char["spirit_root"]
    sr_info = None
    if sr_id and sr_id in SPIRIT_ROOTS:
        sr = SPIRIT_ROOTS[sr_id]
        sr_info = {"id": sr_id, "name": sr["name"], "desc": sr["desc"], "element": sr["element"]}

    # 功法信息（含熟练度）
    prof = get_proficiency(char)
    learned_tech = []
    for tid in (json.loads(char["techniques"]) if char["techniques"] else []):
        if tid in TECHNIQUES:
            t = TECHNIQUES[tid]
            pv = prof.get(tid, 0)
            learned_tech.append({
                "id": tid, "name": t["name"], "tier": t["tier"],
                "proficiency": pv, "max_proficiency": TECHNIQUE_MAX_PROFICIENCY,
                "prof_pct": round(pv / TECHNIQUE_MAX_PROFICIENCY * 100),
            })

    # 经脉信息
    opened_mer = []
    for mid in (json.loads(char["open_meridians"]) if char["open_meridians"] else []):
        if mid in MERIDIANS:
            opened_mer.append({"id": mid, "name": MERIDIANS[mid]["name"]})

    emit("game_state", {
        "char": {
            "name": char["name"], "level": char["level"], "realm": realm_name(char["level"]),
            "exp": char["exp"], "exp_needed": get_exp_needed(char["level"]),
            "hp": char["hp"], "max_hp": stats["max_hp"],
            "atk": stats["atk"], "def": stats["def"],
            "gold": char["gold"], "kills": char["kills"], "deaths": char["deaths"],
            "has_breakthrough_pill": char["has_breakthrough_pill"],
            "cultivation_mult": round(get_cultivation_mult(char), 2),
        },
        "spirit_root": sr_info,
        "techniques": learned_tech,
        "meridians": opened_mer,
        "location": {
            "id": char["location"], "name": loc["name"], "desc": loc["desc"],
            "safe": loc["safe"], "connections": connections_display,
            "npc": loc.get("npc"), "npc_dialog": loc.get("npc_dialog"),
        },
        "inventory": inv_display,
        "equipment": equip_info,
        "pets": get_pet_display_info(char),
        "npcs": get_npc_info_for_location(char),
        "quests": get_quest_info(char),
        "sect": get_sect_info(char),
        "online_count": len(online_users),
        "is_afk": session.get("username", "") in afk_players,
    })


@socketio.on("move")
def handle_move(data):
    if "user_id" not in session: return
    touch_activity(session.get("username", ""))
    char = get_character(session["user_id"])
    if not char: return
    target = data.get("to")
    current_loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
    if target not in current_loc["connections"] or target not in LOCATIONS:
        emit("game_msg", {"text": "此路不通。", "type": "error"})
        return

    new_loc = LOCATIONS[target]
    update_character(session["user_id"], location=target)

    if char["level"] >= 7:
        emit("game_msg", {"text": "你御剑而起，化作一道流光，飞向" + new_loc["name"] + "。", "type": "move"})
    else:
        emit("game_msg", {"text": "你迈步前行，来到了" + new_loc["name"] + "。", "type": "move"})
    emit("game_msg", {"text": new_loc["desc"], "type": "desc"})

    emit("player_moved", {"player": session["username"], "to": target, "to_name": new_loc["name"]}, broadcast=True, include_self=False, namespace="/")

    # 奇遇判定（使用 game.events 模块）
    char = get_character(session["user_id"])
    fortune = check_fortune(char)
    if fortune:
        emit("fortune_event", fortune)

    # 突发事件判定（移动类）
    char = get_character(session["user_id"])
    surprise = process_surprise(char, "move")
    if surprise:
        emit("game_msg", {"text": surprise["text"], "type": "info"})
        _apply_surprise_effect(char, surprise)

    # 任务进度（访问类）
    char = get_character(session["user_id"])
    changed, updated_quests = check_quest_progress(char, "visit", target)
    if changed:
        update_character(session["user_id"], active_quests=json.dumps(updated_quests))

    handle_get_state()


def _apply_surprise_effect(char, surprise):
    """应用突发事件效果"""
    uid = session["user_id"]
    action = surprise.get("action")
    if action == "extra_fight":
        handle_fight()
    elif action == "exp_boost":
        update_character(uid, exp=char["exp"] + surprise["gain"])
        emit("game_msg", {"text": f"修为提升 {surprise['gain']}！", "type": "buff"})
    elif action == "gold_gain":
        update_character(uid, gold=char["gold"] + surprise["gain"])
        emit("game_msg", {"text": f"获得 {surprise['gain']} 灵石。", "type": "shop"})
    elif action == "herb_gain":
        inv = get_character_inventory(uid)
        inv[surprise["herb"]] = inv.get(surprise["herb"], 0) + surprise["count"]
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": f"获得【{ITEMS[surprise['herb']]['name']}】x{surprise['count']}！", "type": "shop"})
    elif action == "heal_partial":
        new_hp = min(char["hp"] + surprise["heal"], surprise["max_hp"])
        update_character(uid, hp=new_hp)
        emit("game_msg", {"text": f"恢复了 {new_hp - char['hp']} 气血。", "type": "heal"})
    elif action == "storm":
        new_hp = max(1, char["hp"] - surprise["hp_loss"])
        update_character(uid, hp=new_hp, exp=char["exp"] + surprise["exp_gain"])
        emit("game_msg", {"text": f"损失 {surprise['hp_loss']} 气血，但修为提升 {surprise['exp_gain']}。", "type": "info"})
    elif action == "item_gain":
        inv = get_character_inventory(uid)
        inv[surprise["item"]] = inv.get(surprise["item"], 0) + surprise["count"]
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": f"获得【{ITEMS[surprise['item']]['name']}】x{surprise['count']}！", "type": "shop"})
    elif action == "loot_cache":
        inv = get_character_inventory(uid)
        for item_id, count, chance in surprise["items"]:
            if random.random() < chance:
                inv[item_id] = inv.get(item_id, 0) + count
                emit("game_msg", {"text": f"获得【{ITEMS[item_id]['name']}】x{count}！", "type": "shop"})
        gold_gain = random.randint(*surprise["gold_range"])
        set_character_inventory(uid, inv)
        update_character(uid, gold=char["gold"] + gold_gain)
    elif action == "material_gain":
        inv = get_character_inventory(uid)
        inv[surprise["mat"]] = inv.get(surprise["mat"], 0) + surprise["count"]
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": f"获得【{ITEMS[surprise['mat']]['name']}】x{surprise['count']}！", "type": "shop"})


@socketio.on("fortune_choice")
def handle_fortune_choice(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return

    event_id = data.get("event_id")
    choice_idx = data.get("choice", 0)

    event = None
    for e in FORTUNE_EVENTS:
        if e["id"] == event_id:
            event = e
            break
    if not event or choice_idx >= len(event["choices"]):
        return

    outcome = event["choices"][choice_idx]["outcome"]
    messages, action = process_fortune_outcome(char, outcome, session["user_id"])
    for m in messages:
        emit("game_msg", m)
    if action == "fight":
        handle_fight()
    handle_get_state()


@socketio.on("fight")
def handle_fight():
    if "user_id" not in session: return
    touch_activity(session.get("username", ""))
    char = get_character(session["user_id"])
    if not char: return

    loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
    if loc["safe"]:
        emit("game_msg", {"text": "青云镇内不可动用灵力，此乃镇规。", "type": "info"})
        return
    pool = loc.get("monster_pool", [])
    if not pool:
        emit("game_msg", {"text": "此处灵气平稳，未察觉妖兽气息。", "type": "info"})
        return

    monster_id = random.choice(pool)
    player_lv = char["level"] + loc.get("level_mod", 0)
    monster = spawn_monster(monster_id, player_level=player_lv)

    stats = get_full_stats(char)
    player_hp = char["hp"]
    player_atk = stats["atk"]
    player_def = stats["def"]
    max_hp = stats["max_hp"]

    # 五行相克
    sr_element = None
    if char["spirit_root"] and char["spirit_root"] in SPIRIT_ROOTS:
        sr_element = SPIRIT_ROOTS[char["spirit_root"]].get("element")
    element_msg = ""
    if sr_element and monster["element"]:
        if ELEMENT_COUNTER.get(sr_element) == monster["element"]:
            player_atk = int(player_atk * 1.3)
            element_msg = f"（{sr_element}克{monster['element']}，攻击+30%）"
        elif ELEMENT_COUNTER.get(monster["element"]) == sr_element:
            player_atk = int(player_atk * 0.8)
            element_msg = f"（{monster['element']}克{sr_element}，攻击-20%）"

    monster_hp = monster["hp"]
    log = [f"—— 妖兽出没！{monster['name']}（{realm_name(monster['level'])}）{element_msg}——"]

    # 战斗类突发事件判定
    for evt in SURPRISE_EVENTS:
        if evt["trigger"] == "fight" and random.random() < evt["chance"]:
            log.append(f"【突发】{evt['text']}")
            eff = evt["effect"]
            if eff == "monster_buff":
                monster[evt["stat"]] = int(monster[evt["stat"]] * evt["mult"])
            elif eff == "monster_debuff":
                monster[evt["stat"]] = max(1, int(monster[evt["stat"]] * evt["mult"]))
            elif eff == "player_buff":
                if evt["stat"] == "atk": player_atk = int(player_atk * evt["mult"])
                elif evt["stat"] == "def": player_def = int(player_def * evt["mult"])
            elif eff == "thunder_strike":
                dmg = random.randint(*evt["dmg_range"])
                monster_hp -= dmg
                log.append(f"天雷造成 {dmg} 点伤害！")
                if monster_hp <= 0:
                    log.append(f"{monster['name']}被天雷劈得灰飞烟灭！")
            elif eff == "extra_monsters":
                extra = random.choice(pool)
                extra_m = spawn_monster(extra, player_level=player_lv)
                monster_hp += extra_m["hp"]
                monster["atk"] = max(monster["atk"], extra_m["atk"])
                log.append(f"增援：{extra_m['name']}（{realm_name(extra_m['level'])}）加入了战斗！")
            elif eff == "bonus_drop":
                pass  # handled after combat
            break  # 只触发一个战斗突发事件

    round_num = 0
    while player_hp > 0 and monster_hp > 0:
        round_num += 1
        p_dmg = max(1, player_atk - monster["def"] + random.randint(-2, 3))
        monster_hp -= p_dmg
        log.append(f"[第{round_num}回合] {fmt_attack(monster['name'])}，造成 {p_dmg} 点伤害。")
        if monster_hp <= 0:
            log.append(f"{monster['name']}哀鸣一声，庞大的身躯轰然倒地，妖丹碎裂，灵气四散！")
            break
        m_dmg = max(1, monster["atk"] - player_def + random.randint(-2, 3))
        player_hp -= m_dmg
        log.append(f"[第{round_num}回合] {fmt_monster_attack(monster['name'])}，你受到 {m_dmg} 点伤害。")

    won = player_hp > 0
    if won:
        gold_gain = monster["gold"] + random.randint(0, monster["gold"] // 2)

        # 熟练度增长
        prof_gained = gain_proficiency(char, session["user_id"], source="fight")
        prof_parts = []
        for tid, amt in prof_gained.items():
            prof_parts.append(f"{TECHNIQUES[tid]['name']}+{amt}")

        prof_msg = f"（{', '.join(prof_parts)}）" if prof_parts else ""
        log.append(f"斗法胜利！获得 {gold_gain} 灵石。{prof_msg}")

        drops = []
        if monster_id in DROP_TABLE:
            for item_id, chance in DROP_TABLE[monster_id]:
                if random.random() < chance:
                    drops.append(item_id)
        # 灵宠蛋掉落
        if monster_id in PET_EGG_MONSTER_DROPS:
            for item_id, chance in PET_EGG_MONSTER_DROPS[monster_id]:
                if random.random() < chance:
                    drops.append(item_id)
        # 藏宝图掉落
        if monster_id in MAP_MONSTER_DROPS:
            for item_id, chance in MAP_MONSTER_DROPS[monster_id]:
                if random.random() < chance:
                    drops.append(item_id)
        # 地点独有掉落
        loc_id = char["location"]
        if loc_id in LOCATION_UNIQUE_DROPS:
            for item_id, chance in LOCATION_UNIQUE_DROPS[loc_id]:
                if random.random() < chance:
                    drops.append(item_id)
        # 战斗突发事件掉落加成
        for evt in SURPRISE_EVENTS:
            if evt["trigger"] == "fight" and evt.get("effect") == "bonus_drop":
                for drop_item in evt.get("item_pool", []):
                    if random.random() < evt.get("drop_chance", 0.5):
                        drops.append(drop_item)

        inv = get_character_inventory(session["user_id"])
        for item_id in drops:
            inv[item_id] = inv.get(item_id, 0) + 1
            log.append(f"天降机缘，获得【{ITEMS[item_id]['name']}】！")
        set_character_inventory(session["user_id"], inv)

        update_character(session["user_id"], hp=player_hp, gold=char["gold"] + gold_gain, kills=char["kills"] + 1)

        # 任务进度（击杀类）
        char = get_character(session["user_id"])
        _check_quest_progress(char, "kill", monster_id)
    else:
        gold_lost = char["gold"] // 5
        # 修为惩罚：损失当前升级所需修为的10%，不低于0
        needed = get_exp_needed(char["level"])
        if needed != "-" and needed > 0:
            exp_lost = min(needed // 10, char["exp"])
        else:
            exp_lost = 0
        # 随机掉落背包物品（15%概率，不掉落装备）
        item_lost_msg = ""
        inv = get_character_inventory(session["user_id"])
        droppable = [iid for iid in inv if inv[iid] > 0 and iid not in (char["weapon"], char["armor"], char["accessory"])]
        if droppable and random.random() < 0.15:
            lost_id = random.choice(droppable)
            inv[lost_id] -= 1
            if inv[lost_id] <= 0:
                del inv[lost_id]
            set_character_inventory(session["user_id"], inv)
            item_lost_msg = f"，遗落了【{ITEMS.get(lost_id, {}).get('name', lost_id)}】"

        death_msgs = [
            "你体内灵力耗尽，不敌妖兽……陨落于此。",
            "妖兽一爪拍下，你口吐鲜血，灵力溃散，倒在血泊之中。",
            "你拼死一搏，终究不敌，意识逐渐模糊……",
            "眼前一黑，元神被妖兽震散，肉身轰然倒地。",
        ]
        log.append(random.choice(death_msgs))
        penalty_parts = [f"损失 {gold_lost} 灵石"]
        if exp_lost > 0:
            penalty_parts.append(f"修为 -{exp_lost}")
        if item_lost_msg:
            penalty_parts.append(item_lost_msg.strip("，"))
        log.append("、".join(penalty_parts) + "，元神被传送回青云镇疗伤。")
        update_character(session["user_id"],
            hp=max_hp // 2,
            gold=max(0, char["gold"] - gold_lost),
            exp=max(0, char["exp"] - exp_lost),
            deaths=char["deaths"] + 1,
            location="qingyun_town")

    emit("fight_log", {"log": log, "won": won})
    # 状态刷新由客户端动画播放完毕后请求


@socketio.on("meditate")
def handle_meditate():
    if "user_id" not in session: return
    touch_activity(session.get("username", ""))
    char = get_character(session["user_id"])
    if not char: return
    loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
    if not loc["safe"]:
        emit("game_msg", {"text": "此处妖气弥漫，无法静心打坐。", "type": "error"})
        return
    stats = get_full_stats(char)
    # 熟练度增长
    prof_gained = gain_proficiency(char, session["user_id"], source="meditate")
    prof_parts = [f"{TECHNIQUES[tid]['name']}+{amt}" for tid, amt in prof_gained.items() if tid in TECHNIQUES]
    prof_msg = f" 熟练度提升（{', '.join(prof_parts)}）。" if prof_parts else ""

    update_character(session["user_id"], hp=stats["max_hp"])

    msgs = [
        f"你盘膝而坐，运转功法，天地灵气涌入体内……气血完全恢复。{prof_msg}",
        f"你闭目凝神，灵力缓缓流转，伤势痊愈，气血充盈。{prof_msg}",
        f"你静心打坐，体悟天地大道，灵台清明，气血恢复如初。{prof_msg}",
    ]
    emit("game_msg", {"text": random.choice(msgs), "type": "heal"})
    handle_get_state()


@socketio.on("breakthrough")
def handle_breakthrough():
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    cur_lv = char["level"]
    if cur_lv >= MAX_LEVEL:
        emit("game_msg", {"text": "你已是大乘期修士，前方唯有飞升一途。", "type": "info"})
        return
    needed = get_exp_needed(cur_lv)
    if needed == "-" or char["exp"] < needed:
        emit("game_msg", {"text": f"修为不足，无法尝试突破。需要 {needed} 修为。", "type": "error"})
        return

    base_chance = BREAKTHROUGH_CHANCE.get(cur_lv, 0.5)
    if char["has_breakthrough_pill"]:
        chance = 1.0
        update_character(session["user_id"], has_breakthrough_pill=0)
        pill_msg = "你服下破境丹，灵台通明，突破毫无阻碍！"
    else:
        chance = base_chance
        pill_msg = ""

    # 突破直接消耗修为
    new_exp = char["exp"] - needed
    update_character(session["user_id"], exp=max(0, new_exp))

    emit("game_msg", {"text": f"你盘膝坐下，消耗 {needed} 修为，运转功法尝试突破……", "type": "info"})
    if pill_msg:
        emit("game_msg", {"text": pill_msg, "type": "buff"})

    if random.random() < chance:
        new_lv = cur_lv + 1
        new_stats = calc_level_stats(new_lv)
        update_character(session["user_id"], level=new_lv, max_hp=new_stats["max_hp"], atk=new_stats["atk"], def_stat=new_stats["def_stat"], hp=new_stats["max_hp"])
        new_realm = realm_name(new_lv)
        logger.info("突破成功：%s -> %s (Lv.%d)", session["username"], new_realm, new_lv)
        emit("game_msg", {"text": f"体内灵力暴涌，丹田剧烈震动——突破成功！你已迈入{new_realm}！", "type": "heal"})
        emit("system_msg", {"text": f"天道感应：{session['username']} 突破至 {new_realm}，引发天地异象！"}, broadcast=True, namespace="/")
    else:
        hp_loss = char["hp"] // 3
        fail_msgs = [
            f"灵力逆行，经脉受损……突破失败！{needed} 修为化为乌有。",
            f"丹田中灵力暴走，冲击境界失败，{needed} 修为付诸东流！",
            f"天地灵气反噬，境界壁垒纹丝不动，{needed} 修为消散于天地间。",
            f"关键时刻心魔入侵，突破功亏一篑，{needed} 修为烟消云散。",
        ]
        emit("game_msg", {"text": random.choice(fail_msgs), "type": "error"})
        update_character(session["user_id"], hp=max(1, char["hp"] - hp_loss))
    handle_get_state()


# ═══════════════ 功法系统 ═══════════════

@socketio.on("learn_technique")
def handle_learn_technique(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    tid = data.get("technique")
    if not tid or tid not in TECHNIQUES:
        return
    t = TECHNIQUES[tid]
    learned = json.loads(char["techniques"]) if char["techniques"] else []

    # 条件1：已学习
    if tid in learned:
        emit("game_msg", {"text": f"你已经领悟了【{t['name']}】。", "type": "error"})
        return
    # 条件2：残卷限定
    if t.get("fragment_only"):
        emit("game_msg", {"text": f"【{t['name']}】只能通过集齐残卷领悟。", "type": "error"})
        return
    # 条件3：境界要求
    if char["level"] < t["req_realm"]:
        emit("game_msg", {"text": f"境界不足，需要{realm_name(t['req_realm'])}才能领悟。", "type": "error"})
        return
    # 条件4：灵根要求
    if t.get("req_element"):
        sr_id = char["spirit_root"]
        sr = SPIRIT_ROOTS.get(sr_id, {})
        sr_element = sr.get("element")
        if sr_element != t["req_element"] and sr_id != "tian" and sr_id != "huntian":
            emit("game_msg", {"text": f"灵根不符，需要{t['req_element']}灵根才能修炼此功法。你的灵根属性为{sr_element or '无属性'}。", "type": "error"})
            return
    # 条件5：前置功法
    if t.get("req_technique"):
        if t["req_technique"] not in learned:
            pre = TECHNIQUES.get(t["req_technique"], {})
            emit("game_msg", {"text": f"需要先领悟【{pre.get('name', t['req_technique'])}】。", "type": "error"})
            return
    # 条件6：灵石消耗
    cost_gold = t.get("cost_gold", t["req_realm"] * 50)
    if char["gold"] < cost_gold:
        emit("game_msg", {"text": f"参悟功法需要 {cost_gold} 灵石，灵石不足。", "type": "error"})
        return
    # 条件7：物品消耗
    cost_items = t.get("cost_items", {})
    if cost_items:
        inv = get_character_inventory(session["user_id"])
        for iid, cnt in cost_items.items():
            if inv.get(iid, 0) < cnt:
                emit("game_msg", {"text": f"需要【{ITEMS.get(iid,{}).get('name',iid)}】x{cnt}，材料不足。", "type": "error"})
                return
        for iid, cnt in cost_items.items():
            inv[iid] -= cnt
            if inv[iid] <= 0: del inv[iid]
        set_character_inventory(session["user_id"], inv)
    # 条件8：正魔道冲突检查
    if t.get("alignment") and t["alignment"] != "中立":
        for lid in learned:
            lt = TECHNIQUES.get(lid, {})
            la = lt.get("alignment", "中立")
            if la != "中立" and la != t["alignment"]:
                conflict_key = (la, t["alignment"])
                if ALIGNMENT_CONFLICTS.get(conflict_key, 0) > 0:
                    emit("game_msg", {"text": f"警告：【{t['name']}】（{t['alignment']}）与已学【{lt['name']}】（{la}）存在道法冲突！同时修炼可能影响突破。", "type": "error"})
                    # 仍然允许学习，但发出警告

    # 扣除灵石并学习
    learned.append(tid)
    update_character(session["user_id"], techniques=json.dumps(learned), gold=char["gold"] - cost_gold)
    emit("game_msg", {"text": f"你耗费 {cost_gold} 灵石，潜心参悟，终于领悟了【{t['name']}】（{t['tier']}）！", "type": "buff"})
    handle_get_state()


# ═══════════════ 经脉系统 ═══════════════

@socketio.on("open_meridian")
def handle_open_meridian(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    mid = data.get("meridian")
    if not mid or mid not in MERIDIANS:
        return
    m = MERIDIANS[mid]
    opened = json.loads(char["open_meridians"]) if char["open_meridians"] else []
    if mid in opened:
        emit("game_msg", {"text": f"你的{m['name']}已经打通。", "type": "error"})
        return
    if char["level"] < m["req_realm"]:
        emit("game_msg", {"text": f"境界不足，需要{realm_name(m['req_realm'])}才能打通。", "type": "error"})
        return
    if char["exp"] < m["cost"]:
        emit("game_msg", {"text": f"打通{m['name']}需要 {m['cost']} 修为，修为不足。", "type": "error"})
        return
    opened.append(mid)
    update_character(session["user_id"], open_meridians=json.dumps(opened), exp=char["exp"] - m["cost"])
    emit("game_msg", {"text": f"你消耗 {m['cost']} 修为，冲击{m['name']}……经脉畅通，灵力大增！", "type": "buff"})
    handle_get_state()


# ═══════════════ 炼丹系统 ═══════════════

@socketio.on("refine_pill")
def handle_refine_pill(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
    if not loc["safe"]:
        emit("game_msg", {"text": "炼丹需要在安全区域进行。", "type": "error"})
        return
    recipe_id = data.get("recipe")
    if not recipe_id or recipe_id not in RECIPES:
        return
    recipe = RECIPES[recipe_id]
    if char["level"] < recipe["req_realm"]:
        emit("game_msg", {"text": f"境界不足，需要{realm_name(recipe['req_realm'])}才能炼制。", "type": "error"})
        return
    inv = get_character_inventory(session["user_id"])
    for mat, count in recipe["ingredients"].items():
        if inv.get(mat, 0) < count:
            emit("game_msg", {"text": f"材料不足！需要{ITEMS[mat]['name']} x{count}。", "type": "error"})
            return
    for mat, count in recipe["ingredients"].items():
        inv[mat] -= count
        if inv[mat] <= 0: del inv[mat]
    output = recipe["output"]
    inv[output] = inv.get(output, 0) + recipe["output_count"]
    set_character_inventory(session["user_id"], inv)
    emit("game_msg", {"text": f"你将灵草投入丹炉，运转灵力催动丹火……丹成！获得【{ITEMS[output]['name']}】x{recipe['output_count']}！", "type": "heal"})
    handle_get_state()


# ═══════════════ 炼器系统 ═══════════════

@socketio.on("forge_item")
def handle_forge_item(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
    if not loc["safe"]:
        emit("game_msg", {"text": "炼器需要在安全区域进行。", "type": "error"})
        return

    recipe_id = data.get("recipe")
    if not recipe_id or recipe_id not in FORGE_RECIPES:
        return
    recipe = FORGE_RECIPES[recipe_id]

    if char["level"] < recipe["req_realm"]:
        emit("game_msg", {"text": f"境界不足，需要{realm_name(recipe['req_realm'])}才能锻造。", "type": "error"})
        return

    inv = get_character_inventory(session["user_id"])
    for mat, count in recipe["ingredients"].items():
        if inv.get(mat, 0) < count:
            emit("game_msg", {"text": f"材料不足！需要{ITEMS[mat]['name']} x{count}。", "type": "error"})
            return

    for mat, count in recipe["ingredients"].items():
        inv[mat] -= count
        if inv[mat] <= 0: del inv[mat]
    set_character_inventory(session["user_id"], inv)

    base_rate = recipe["success_rate"]
    realm_bonus = max(0, char["level"] - recipe["req_realm"]) * FORGE_REALM_BONUS_PER_LV
    final_rate = min(0.99, base_rate + realm_bonus)

    mat_names = "、".join([f"{ITEMS[m]['name']}x{c}" for m, c in recipe["ingredients"].items()])
    log_lines = [f"你将{mat_names}投入器炉，运转灵力催动炉火……"]

    if random.random() < final_rate:
        item_id, item_data = generate_equip(recipe["slot"], recipe["tier"])
        inv = get_character_inventory(session["user_id"])
        inv[item_id] = inv.get(item_id, 0) + 1
        set_character_inventory(session["user_id"], inv)
        pct = int(final_rate * 100)
        log_lines.append(f"炉中光芒大放！锻造成功（{pct}%）——获得【{item_data['name']}】！{item_data['grade']} {item_data['desc']}")
        emit("forge_log", {"log": log_lines, "success": True})
    else:
        pct = int(final_rate * 100)
        log_lines.append(f"炉火骤然熄灭，材料化为灰烬……锻造失败（{pct}%成功率）。")
        emit("forge_log", {"log": log_lines, "success": False})

    handle_get_state()


@socketio.on("get_forge_recipes")
def handle_get_forge_recipes():
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    inv = get_character_inventory(session["user_id"])

    recipes = []
    for rid, r in FORGE_RECIPES.items():
        can_craft = char["level"] >= r["req_realm"]
        for mat, count in r["ingredients"].items():
            if inv.get(mat, 0) < count:
                can_craft = False
        base_rate = r["success_rate"]
        realm_bonus = max(0, char["level"] - r["req_realm"]) * FORGE_REALM_BONUS_PER_LV
        final_rate = min(0.99, base_rate + realm_bonus)
        slot_name = {"weapon": "武器", "armor": "护甲", "accessory": "饰品"}[r["slot"]]
        recipes.append({
            "id": rid, "name": r["name"], "slot": r["slot"], "slot_name": slot_name,
            "tier": r["tier"], "success_rate": int(final_rate * 100),
            "req_realm": realm_name(r["req_realm"]), "can_craft": can_craft,
            "ingredients": [{"name": ITEMS[m]["name"], "need": c, "have": inv.get(m, 0)} for m, c in r["ingredients"].items()],
        })
    emit("forge_recipes", {"data": recipes})


# ═══════════════ 其他事件 ═══════════════

@socketio.on("use_item")
def handle_use_item(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    item_id = data.get("item")
    if not item_id: return
    item = lookup_item(item_id)
    if not item: return
    inv = get_character_inventory(session["user_id"])
    if inv.get(item_id, 0) <= 0:
        emit("game_msg", {"text": "你没有此物。", "type": "error"})
        return
    if item["type"] == "material":
        emit("game_msg", {"text": "灵草是炼丹材料，不可直接使用。", "type": "info"})
        return
    if item["type"] == "pet_egg":
        handle_hatch_egg({"item": item_id})
        return
    if item["type"] == "pet_food":
        emit("game_msg", {"text": "灵兽饲料请在灵宠面板中喂养。", "type": "info"})
        return
    if item["type"] == "treasure_map":
        handle_use_map({"item": item_id})
        return
    if item["type"] == "map_upgrade":
        emit("game_msg", {"text": "寻宝罗盘请在储物袋中对藏宝图使用。", "type": "info"})
        return
    if item["type"] == "technique_fragment":
        handle_combine_fragments({"group": item["fragment_group"]})
        return

    if item["type"] == "consumable":
        if item["effect"] == "heal":
            stats = get_full_stats(char)
            new_hp = min(char["hp"] + item["value"], stats["max_hp"])
            healed = new_hp - char["hp"]
            inv[item_id] -= 1
            if inv[item_id] <= 0: del inv[item_id]
            set_character_inventory(session["user_id"], inv)
            update_character(session["user_id"], hp=new_hp)
            emit("game_msg", {"text": f"你服下【{item['name']}】，药力化开，恢复了 {healed} 气血。", "type": "heal"})
        elif item["effect"] == "heal_full":
            stats = get_full_stats(char)
            inv[item_id] -= 1
            if inv[item_id] <= 0: del inv[item_id]
            set_character_inventory(session["user_id"], inv)
            update_character(session["user_id"], hp=stats["max_hp"])
            emit("game_msg", {"text": f"你服下【{item['name']}】，灵丹妙药，气血完全恢复！", "type": "heal"})
        elif item["effect"] == "exp":
            inv[item_id] -= 1
            if inv[item_id] <= 0: del inv[item_id]
            set_character_inventory(session["user_id"], inv)
            update_character(session["user_id"], exp=char["exp"] + item["value"])
            emit("game_msg", {"text": f"你服下【{item['name']}】，灵力涌入丹田，修为提升 {item['value']}。", "type": "buff"})
        elif item["effect"] == "breakthrough":
            inv[item_id] -= 1
            if inv[item_id] <= 0: del inv[item_id]
            set_character_inventory(session["user_id"], inv)
            update_character(session["user_id"], has_breakthrough_pill=1)
            emit("game_msg", {"text": f"你收好【{item['name']}】，下次突破时将自动使用。", "type": "buff"})
        elif item["effect"] == "combat_buff":
            inv[item_id] -= 1
            if inv[item_id] <= 0: del inv[item_id]
            set_character_inventory(session["user_id"], inv)
            update_character(session["user_id"], combat_buff=item["value"])
            emit("game_msg", {"text": f"你服下【{item['name']}】，灵力暴涨，下次战斗伤害提升{item['value']}%！", "type": "buff"})
        elif item["effect"] == "hp_up":
            inv[item_id] -= 1
            if inv[item_id] <= 0: del inv[item_id]
            set_character_inventory(session["user_id"], inv)
            update_character(session["user_id"], max_hp=char["max_hp"] + item["value"], hp=char["hp"] + item["value"])
            emit("game_msg", {"text": f"你催动【{item['name']}】，符箓化作灵光涌入丹田，气血上限永久 +{item['value']}！", "type": "buff"})
        elif item["effect"] == "atk_up":
            inv[item_id] -= 1
            if inv[item_id] <= 0: del inv[item_id]
            set_character_inventory(session["user_id"], inv)
            update_character(session["user_id"], atk=char["atk"] + item["value"])
            emit("game_msg", {"text": f"你催动【{item['name']}】，符箓化作灵光融入体内，攻击永久 +{item['value']}！", "type": "buff"})
        elif item["effect"] == "def_up":
            inv[item_id] -= 1
            if inv[item_id] <= 0: del inv[item_id]
            set_character_inventory(session["user_id"], inv)
            update_character(session["user_id"], def_stat=char["def_stat"] + item["value"])
            emit("game_msg", {"text": f"你催动【{item['name']}】，符箓化作灵光护体，防御永久 +{item['value']}！", "type": "buff"})
    elif item["type"] == "equip":
        slot = item["slot"]
        if slot == "weapon":
            old = char["weapon"]
            update_character(session["user_id"], weapon=item_id)
        elif slot == "armor":
            old = char["armor"]
            update_character(session["user_id"], armor=item_id)
        elif slot == "accessory":
            old = char["accessory"]
            update_character(session["user_id"], accessory=item_id)
        else:
            return
        inv[item_id] -= 1
        if inv[item_id] <= 0: del inv[item_id]
        if old: inv[old] = inv.get(old, 0) + 1
        set_character_inventory(session["user_id"], inv)
        emit("game_msg", {"text": f"你祭炼【{item['name']}】，将其纳为己用。", "type": "equip"})
    handle_get_state()


@socketio.on("unequip")
def handle_unequip(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    slot = data.get("slot")
    if slot not in ("weapon", "armor", "accessory"): return
    current = char["weapon"] if slot == "weapon" else (char["armor"] if slot == "armor" else char["accessory"])
    if not current:
        emit("game_msg", {"text": "该位置无法宝。", "type": "error"})
        return
    inv = get_character_inventory(session["user_id"])
    inv[current] = inv.get(current, 0) + 1
    set_character_inventory(session["user_id"], inv)
    if slot == "weapon": update_character(session["user_id"], weapon=None)
    elif slot == "armor": update_character(session["user_id"], armor=None)
    else: update_character(session["user_id"], accessory=None)
    cur_item = lookup_item(current)
    emit("game_msg", {"text": f"你收回了【{cur_item['name'] if cur_item else current}】。", "type": "equip"})
    handle_get_state()


@socketio.on("item_detail")
def handle_item_detail(data):
    """返回物品详细信息及获取途径"""
    if "user_id" not in session: return
    item_id = data.get("item")
    if not item_id: return
    item = lookup_item(item_id)
    if not item: return

    sources = []

    # 1. 坊市购买
    _shop_items = [
        "huiqi_dan", "huichun_dan", "peiyuan_dan", "dingdan",
        "liliang_fulu", "huti_fulu", "tiemu_sword", "cloth_robe",
        "qingyu_peidai", "tongqian_hufu", "egg_common", "pet_feed",
    ]
    if item_id in _shop_items:
        sources.append("坊市购买")

    # 2. 怪物掉落
    monster_names = []
    for mid, drops in DROP_TABLE.items():
        for did, _ in drops:
            if did == item_id:
                monster_names.append(MONSTERS.get(mid, {}).get("name", mid))
    for mid, drops in MAP_MONSTER_DROPS.items():
        for did, _ in drops:
            if did == item_id and MONSTERS.get(mid, {}).get("name", mid) not in monster_names:
                monster_names.append(MONSTERS.get(mid, {}).get("name", mid))
    for mid, drops in PET_EGG_MONSTER_DROPS.items():
        for did, _ in drops:
            if did == item_id and MONSTERS.get(mid, {}).get("name", mid) not in monster_names:
                monster_names.append(MONSTERS.get(mid, {}).get("name", mid))
    if monster_names:
        sources.append(f"斩妖掉落（{', '.join(monster_names[:5])}{'等' if len(monster_names) > 5 else ''}）")

    # 3. 地点独有
    loc_names = []
    for loc_id, drops in LOCATION_UNIQUE_DROPS.items():
        for did, _ in drops:
            if did == item_id:
                loc_names.append(LOCATIONS.get(loc_id, {}).get("name", loc_id))
    if loc_names:
        sources.append(f"独有产出（{', '.join(loc_names)}）")

    # 4. 炼丹/炼器
    for rid, r in RECIPES.items():
        if r.get("result") == item_id:
            sources.append(f"炼丹获得（{r['name']}）")
            break
    for rid, r in FORGE_RECIPES.items():
        if r.get("result_slot"):
            sources.append("炼器锻造")
            break

    # 5. 拍卖行
    if item_id in [p["id"] for p in AUCTION_POOL]:
        sources.append("拍卖行竞拍")

    # 6. 宝藏
    if item.get("type") == "treasure_map":
        sources.append("使用后探索宝藏")
    if item.get("type") == "map_upgrade":
        sources.append("高级怪物掉落")

    # 7. 功法残卷
    if item.get("type") == "technique_fragment":
        sources.append("宝藏探索获得")

    if not sources:
        sources.append("探索世界获取")

    # 效果描述
    effect = ""
    if item.get("type") == "consumable":
        eff = item.get("effect", "")
        if eff == "heal": effect = f"使用后恢复{item.get('value', 0)}气血"
        elif eff == "heal_full": effect = "使用后气血完全恢复"
        elif eff == "exp": effect = f"使用后获得{item.get('value', 0)}修为"
        elif eff == "breakthrough": effect = "下次突破必定成功"
        elif eff == "combat_buff": effect = f"下次战斗伤害+{item.get('value', 0)}%"
        elif eff == "atk_up": effect = f"永久增加{item.get('value', 0)}攻击"
        elif eff == "def_up": effect = f"永久增加{item.get('value', 0)}防御"
        elif eff == "hp_up": effect = f"永久增加{item.get('value', 0)}气血上限"
    elif item.get("type") == "equip":
        parts = []
        if item.get("atk"): parts.append(f"攻击+{item['atk']}")
        if item.get("def"): parts.append(f"防御+{item['def']}")
        if item.get("bonus_hp"): parts.append(f"气血+{item['bonus_hp']}")
        effect = "、".join(parts) if parts else ""
    elif item.get("type") == "pet_food":
        effect = f"灵宠经验+{item.get('pet_exp', 0)}"
    elif item.get("type") == "pet_egg":
        tiers = {"common": "普通", "rare": "稀有", "legend": "传说"}
        effect = f"{tiers.get(item.get('egg_tier', ''), '')}灵兽蛋，点击孵化"

    emit("item_detail", {
        "id": item_id,
        "name": item["name"],
        "desc": item.get("desc", ""),
        "effect": effect,
        "sources": sources,
    })


@socketio.on("buy_item")
def handle_buy_item(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
    if not loc["safe"]:
        emit("game_msg", {"text": "坊市只在青云镇开放。", "type": "error"})
        return
    item_id = data.get("item")
    if not item_id or item_id not in ITEMS: return
    item = ITEMS[item_id]
    if item["price"] > char["gold"]:
        emit("game_msg", {"text": f"灵石不足！需要 {item['price']} 灵石。", "type": "error"})
        return
    inv = get_character_inventory(session["user_id"])
    inv[item_id] = inv.get(item_id, 0) + 1
    set_character_inventory(session["user_id"], inv)
    update_character(session["user_id"], gold=char["gold"] - item["price"])
    emit("game_msg", {"text": f"你在坊市购得【{item['name']}】，花费 {item['price']} 灵石。", "type": "shop"})
    handle_get_state()


@socketio.on("chat")
def handle_chat(data):
    if "username" not in session: return
    touch_activity(session.get("username", ""))
    text = data.get("text", "").strip()
    if not text or len(text) > 200: return
    emit("chat_msg", {"from": session["username"], "text": text}, broadcast=True)


@socketio.on("get_leaderboard")
def handle_leaderboard():
    rows = get_leaderboard()
    lb = [{"name": r["name"], "level": r["level"], "realm": realm_name(r["level"]), "exp": r["exp"], "kills": r["kills"]} for r in rows]
    emit("leaderboard", {"data": lb})


@socketio.on("get_techniques")
def handle_get_techniques():
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    sr_id = char["spirit_root"]
    sr = SPIRIT_ROOTS.get(sr_id, {})
    sr_element = sr.get("element")
    is_tian = sr_id in ("tian", "huntian")

    available = []
    for tid, t in TECHNIQUES.items():
        if tid in learned: continue
        if t.get("fragment_only"): continue  # 残卷功法不在列表显示

        cost_gold = t.get("cost_gold", t["req_realm"] * 50)
        cost_items = t.get("cost_items", {})

        # 检查所有条件
        reasons = []
        can_learn = True
        if char["level"] < t["req_realm"]:
            reasons.append(f"需{realm_name(t['req_realm'])}")
            can_learn = False
        if t.get("req_element") and not is_tian and sr_element != t["req_element"]:
            reasons.append(f"需{t['req_element']}灵根")
            can_learn = False
        if t.get("req_technique") and t["req_technique"] not in learned:
            pre_name = TECHNIQUES.get(t["req_technique"], {}).get("name", "?")
            reasons.append(f"需先学{pre_name}")
            can_learn = False
        if char["gold"] < cost_gold:
            reasons.append(f"需{cost_gold}灵石")
            can_learn = False
        for iid, cnt in cost_items.items():
            reasons.append(f"需{ITEMS.get(iid,{}).get('name','?')}x{cnt}")

        alignment = t.get("alignment", "中立")
        # 检查正魔道冲突
        has_conflict = False
        if alignment != "中立":
            for lid in learned:
                lt = TECHNIQUES.get(lid, {})
                la = lt.get("alignment", "中立")
                if la != "中立" and la != alignment:
                    has_conflict = True
                    break

        available.append({
            "id": tid, "name": t["name"], "tier": t["tier"], "desc": t["desc"],
            "req_realm": realm_name(t["req_realm"]), "cost_gold": cost_gold,
            "cost_items": [{"name": ITEMS.get(iid,{}).get("name","?"), "need": cnt} for iid, cnt in cost_items.items()],
            "req_element": t.get("req_element"),
            "req_technique": t.get("req_technique"),
            "alignment": alignment,
            "reasons": reasons,
            "can_learn": can_learn,
            "has_conflict": has_conflict,
        })
    emit("techniques_list", {"available": available, "learned": learned})


@socketio.on("get_meridians")
def handle_get_meridians():
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    opened = json.loads(char["open_meridians"]) if char["open_meridians"] else []
    available = []
    for mid, m in MERIDIANS.items():
        status = "opened" if mid in opened else ("unlockable" if char["level"] >= m["req_realm"] and char["exp"] >= m["cost"] else "locked")
        available.append({"id": mid, "name": m["name"], "desc": m["desc"], "cost": m["cost"],
                          "req_realm": realm_name(m["req_realm"]), "status": status,
                          "bonus": f"气血+{m['bonus_hp']} 攻击+{m['bonus_atk']} 防御+{m['bonus_def']}"})
    emit("meridians_list", {"data": available, "opened": opened})


# ═══════════════ 灵宠系统 ═══════════════

def get_pet_display_info(char):
    """获取角色所有灵宠的展示信息"""
    pets = json.loads(char["pets"]) if char["pets"] else []
    active_pet_id = char["active_pet"]
    result = []
    for pet in pets:
        species = PET_SPECIES.get(pet["species_id"], {})
        stats = get_pet_stats(pet)
        needed = get_pet_exp_needed(pet["level"])
        result.append({
            "id": pet["id"],
            "species_id": pet["species_id"],
            "name": species.get("name", "未知"),
            "rarity": species.get("rarity", "common"),
            "element": species.get("element"),
            "desc": species.get("desc", ""),
            "level": pet["level"],
            "exp": pet["exp"],
            "exp_needed": needed,
            "hp": stats["hp"],
            "atk": stats["atk"],
            "def": stats["def"],
            "is_active": pet["id"] == active_pet_id,
        })
    return result


@socketio.on("hatch_egg")
def handle_hatch_egg(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    item_id = data.get("item")
    if not item_id: return
    item = lookup_item(item_id)
    if not item or item.get("type") != "pet_egg":
        return

    inv = get_character_inventory(session["user_id"])
    if inv.get(item_id, 0) <= 0:
        emit("game_msg", {"text": "你没有这枚灵兽蛋。", "type": "error"})
        return

    inv[item_id] -= 1
    if inv[item_id] <= 0: del inv[item_id]
    set_character_inventory(session["user_id"], inv)

    egg_tier = item["egg_tier"]
    species_id, species = hatch_egg(egg_tier)

    import uuid
    pet_id = str(uuid.uuid4())[:8]
    new_pet = {"id": pet_id, "species_id": species_id, "level": 1, "exp": 0}

    pets = json.loads(char["pets"]) if char["pets"] else []
    pets.append(new_pet)
    update_character(session["user_id"], pets=json.dumps(pets))

    rarity_names = {"common": "普通", "rare": "稀有", "legend": "传说"}
    emit("game_msg", {
        "text": f"你将灵力注入灵兽蛋，蛋壳裂开，一只【{species['name']}】（{rarity_names[species['rarity']]}）破壳而出！它用小脑袋蹭了蹭你的手心。",
        "type": "heal",
    })
    handle_get_state()


@socketio.on("feed_pet")
def handle_feed_pet(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    pet_id = data.get("pet_id")
    item_id = data.get("item")
    if not pet_id or not item_id: return
    item = lookup_item(item_id)
    if not item or item.get("type") != "pet_food":
        return

    inv = get_character_inventory(session["user_id"])
    if inv.get(item_id, 0) <= 0:
        emit("game_msg", {"text": "你没有这个食物。", "type": "error"})
        return

    pets = json.loads(char["pets"]) if char["pets"] else []
    target_pet = None
    for pet in pets:
        if pet["id"] == pet_id:
            target_pet = pet
            break
    if not target_pet:
        emit("game_msg", {"text": "未找到该灵宠。", "type": "error"})
        return

    if target_pet["level"] >= PET_MAX_LEVEL:
        emit("game_msg", {"text": "灵宠已达最高等级。", "type": "error"})
        return

    inv[item_id] -= 1
    if inv[item_id] <= 0: del inv[item_id]
    set_character_inventory(session["user_id"], inv)

    target_pet["exp"] += item["pet_exp"]
    species = PET_SPECIES.get(target_pet["species_id"], {})
    level_up_msgs = []
    while target_pet["level"] < PET_MAX_LEVEL:
        needed = get_pet_exp_needed(target_pet["level"])
        if target_pet["exp"] >= needed:
            target_pet["exp"] -= needed
            target_pet["level"] += 1
            level_up_msgs.append(f"【{species.get('name', '灵宠')}】升到了 Lv.{target_pet['level']}！")
        else:
            break

    update_character(session["user_id"], pets=json.dumps(pets))
    emit("game_msg", {"text": f"你喂了【{species.get('name', '灵宠')}】一份{item['name']}，成长经验+{item['pet_exp']}。", "type": "heal"})
    for msg in level_up_msgs:
        emit("game_msg", {"text": msg, "type": "buff"})
    handle_get_state()


@socketio.on("activate_pet")
def handle_activate_pet(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    pet_id = data.get("pet_id")
    if not pet_id: return
    pets = json.loads(char["pets"]) if char["pets"] else []
    found = any(p["id"] == pet_id for p in pets)
    if not found:
        emit("game_msg", {"text": "未找到该灵宠。", "type": "error"})
        return
    update_character(session["user_id"], active_pet=pet_id)
    species = PET_SPECIES.get(next(p["species_id"] for p in pets if p["id"] == pet_id), {})
    emit("game_msg", {"text": f"你将【{species.get('name', '灵宠')}】设为出战灵宠。", "type": "equip"})
    handle_get_state()


@socketio.on("deactivate_pet")
def handle_deactivate_pet():
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    update_character(session["user_id"], active_pet=None)
    emit("game_msg", {"text": "你收回了出战灵宠。", "type": "equip"})
    handle_get_state()


# ═══════════════ 藏宝图系统 ═══════════════

@socketio.on("use_map")
def handle_use_map(data):
    """使用藏宝图寻宝"""
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    item_id = data.get("item")
    if not item_id: return
    item = lookup_item(item_id)
    if not item or item.get("type") != "treasure_map":
        return

    inv = get_character_inventory(session["user_id"])
    if inv.get(item_id, 0) <= 0:
        emit("game_msg", {"text": "你没有这张藏宝图。", "type": "error"})
        return

    inv[item_id] -= 1
    if inv[item_id] <= 0: del inv[item_id]

    tier = item["map_tier"]
    table = TREASURE_TABLES[tier]
    tier_names = {1: "残破", 2: "完整", 3: "上古"}
    log_lines = [f"你展开{tier_names[tier]}藏宝图，循着标记的方向前行……"]

    # 战斗判定
    fought = False
    if random.random() < table["combat_chance"]:
        monster_id = random.choice(table["combat_monsters"])
        monster = spawn_monster(monster_id, player_level=char["level"])
        log_lines.append(f"突然！一只{monster['name']}（{realm_name(monster['level'])}）从暗处扑出，守护宝藏！")
        # 简化战斗
        stats = get_full_stats(char)
        player_hp = char["hp"]
        monster_hp = monster["hp"]
        rnd = 0
        while player_hp > 0 and monster_hp > 0:
            rnd += 1
            p_dmg = max(1, stats["atk"] - monster["def"] + random.randint(-2, 3))
            monster_hp -= p_dmg
            log_lines.append(f"[第{rnd}回合] {fmt_attack(monster['name'])}，造成 {p_dmg} 点伤害。")
            if monster_hp <= 0:
                log_lines.append(f"{monster['name']}倒下了！你继续向宝藏前进。")
                break
            m_dmg = max(1, monster["atk"] - stats["def"] + random.randint(-2, 3))
            player_hp -= m_dmg
            log_lines.append(f"[第{rnd}回合] {fmt_monster_attack(monster['name'])}，受到 {m_dmg} 点伤害。")
        fought = True
        if player_hp <= 0:
            log_lines.append("你不敌守宝妖兽，藏宝图在战斗中损毁……")
            update_character(session["user_id"], hp=max(1, stats["max_hp"] // 3),
                             gold=max(0, char["gold"] - 20), deaths=char["deaths"] + 1)
            set_character_inventory(session["user_id"], inv)
            emit("fight_log", {"log": log_lines, "won": False})
            return
        # 更新战斗后的HP
        update_character(session["user_id"], hp=player_hp)
        char = get_character(session["user_id"])

    # 获得奖励
    gold_gain = random.randint(*table["gold_range"])
    exp_gain = random.randint(*table["exp_range"])
    log_lines.append(f"你找到了宝藏！获得 {gold_gain} 灵石、{exp_gain} 修为。")

    item_count = random.randint(*table["item_count"])
    rewards = []
    for _ in range(item_count):
        r = random.random()
        cum = 0
        for iid, chance in table["item_pool"]:
            cum += chance
            if r < cum:
                rewards.append(iid)
                break

    # 功法残卷
    if random.random() < table.get("fragment_chance", 0):
        frag_pool = table.get("fragment_pool", [])
        if frag_pool:
            frag = random.choice(frag_pool)
            rewards.append(frag)

    for iid in rewards:
        inv[iid] = inv.get(iid, 0) + 1
        log_lines.append(f"获得【{ITEMS[iid]['name']}】！")

    set_character_inventory(session["user_id"], inv)
    update_character(session["user_id"], exp=char["exp"] + exp_gain, gold=char["gold"] + gold_gain)

    emit("fight_log", {"log": log_lines, "won": True})


@socketio.on("upgrade_map")
def handle_upgrade_map(data):
    """使用寻宝罗盘升级藏宝图"""
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    item_id = data.get("item")
    if not item_id: return
    item = lookup_item(item_id)
    if not item or item.get("type") != "treasure_map":
        emit("game_msg", {"text": "只能对藏宝图使用。", "type": "error"})
        return
    if item["map_tier"] >= 3:
        emit("game_msg", {"text": "已经是最高品质的藏宝图了。", "type": "error"})
        return

    # 等级限制
    upgrade_req = {1: 5, 2: 10}  # tier1→2 需要5级，tier2→3 需要10级
    req_lv = upgrade_req.get(item["map_tier"], 99)
    if char["level"] < req_lv:
        emit("game_msg", {"text": f"境界不足！升级需要{realm_name(req_lv)}（当前{realm_name(char['level'])}）。", "type": "error"})
        return

    # 材料限制
    upgrade_mats = {
        1: {"yaogu": 3, "hantie_kuang": 2},       # 残破→完整
        2: {"yaodan": 2, "xuanjin_shi": 3, "tianwai_yuntie": 1},  # 完整→上古
    }
    need_mats = upgrade_mats.get(item["map_tier"], {})

    inv = get_character_inventory(session["user_id"])
    if inv.get("map_compass", 0) <= 0:
        emit("game_msg", {"text": "你没有寻宝罗盘。", "type": "error"})
        return
    if inv.get(item_id, 0) <= 0:
        emit("game_msg", {"text": "你没有这张藏宝图。", "type": "error"})
        return

    # 检查材料
    missing = []
    for mat_id, need in need_mats.items():
        have = inv.get(mat_id, 0)
        if have < need:
            mat_name = ITEMS.get(mat_id, {}).get("name", mat_id)
            missing.append(f"{mat_name}({have}/{need})")
    if missing:
        emit("game_msg", {"text": f"材料不足：{'、'.join(missing)}", "type": "error"})
        return

    # 扣除材料 + 罗盘 + 旧图
    new_tier = item["map_tier"] + 1
    new_map_id = {2: "map_rare", 3: "map_legend"}[new_tier]
    for mat_id, need in need_mats.items():
        inv[mat_id] -= need
        if inv[mat_id] <= 0: del inv[mat_id]
    inv[item_id] -= 1
    if inv[item_id] <= 0: del inv[item_id]
    inv["map_compass"] -= 1
    if inv["map_compass"] <= 0: del inv["map_compass"]
    inv[new_map_id] = inv.get(new_map_id, 0) + 1
    set_character_inventory(session["user_id"], inv)

    tier_names = {2: "完整藏宝图", 3: "上古藏宝图"}
    emit("game_msg", {"text": f"寻宝罗盘灵光闪烁，藏宝图品质提升！获得【{tier_names[new_tier]}】！", "type": "buff"})
    handle_get_state()


@socketio.on("combine_fragments")
def handle_combine_fragments(data):
    """合成功法残卷"""
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    group = data.get("group")
    if not group or group not in FRAGMENT_RECIPES:
        return

    technique_id, fragments = FRAGMENT_RECIPES[group]
    if technique_id in TECHNIQUES:
        t = TECHNIQUES[technique_id]
        learned = json.loads(char["techniques"]) if char["techniques"] else []
        if technique_id in learned:
            emit("game_msg", {"text": f"你已经领悟了【{t['name']}】。", "type": "error"})
            return
        if char["level"] < t["req_realm"]:
            emit("game_msg", {"text": f"境界不足，需要{realm_name(t['req_realm'])}才能领悟。", "type": "error"})
            return

    inv = get_character_inventory(session["user_id"])
    for frag_id in fragments:
        if inv.get(frag_id, 0) <= 0:
            frag_name = ITEMS.get(frag_id, {}).get("name", frag_id)
            emit("game_msg", {"text": f"缺少【{frag_name}】，无法合成。", "type": "error"})
            return

    # 扣除残卷
    for frag_id in fragments:
        inv[frag_id] -= 1
        if inv[frag_id] <= 0: del inv[frag_id]
    set_character_inventory(session["user_id"], inv)

    # 学习功法
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    if technique_id not in learned:
        learned.append(technique_id)
        update_character(session["user_id"], techniques=json.dumps(learned))

    t = TECHNIQUES.get(technique_id, {})
    names = "、".join([ITEMS.get(f,{}).get("name","?") for f in fragments])
    emit("game_msg", {"text": f"你将{names}拼合在一起，残卷上的文字忽然流转起来——领悟了完整功法【{t.get('name', technique_id)}】（{t.get('tier', '')}）！", "type": "buff"})
    handle_get_state()


# ═══════════════ NPC系统（使用 game.npc 模块） ═══════════════


@socketio.on("npc_interact")
def handle_npc_interact(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    nid = data.get("npc_id")

    result = interact_with_npc(char, session["user_id"], nid)
    if not result["success"]:
        if result.get("message"):
            emit("game_msg", {"text": result["message"], "type": "error"})
        return

    if result["goodwill_changed"]:
        update_character(session["user_id"],
                         npc_goodwill=json.dumps(result["updated_goodwill"]),
                         npc_gift_date=json.dumps(result["updated_gift_dates"]))

    emit("npc_detail", result["detail"])


@socketio.on("npc_gift")
def handle_npc_gift(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    nid = data.get("npc_id")
    item_id = data.get("item")

    inv = get_character_inventory(session["user_id"])
    result = give_npc_gift(char, inv, nid, item_id)

    if not result["success"]:
        emit("game_msg", {"text": result["message"], "type": "error"})
        return

    set_character_inventory(session["user_id"], result["updated_inv"])
    update_character(session["user_id"],
                     npc_goodwill=json.dumps(result["updated_goodwill"]),
                     npc_gift_date=json.dumps(result["updated_gift_dates"]))
    mtype = "heal" if "好感度+" in result["message"] else "error"
    emit("game_msg", {"text": result["message"], "type": mtype})
    handle_get_state()


@socketio.on("quest_accept")
def handle_quest_accept(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    qid = data.get("quest_id")

    result = accept_quest(char, qid)
    if not result["success"]:
        emit("game_msg", {"text": result.get("message", ""), "type": "error"})
        return

    update_character(session["user_id"], active_quests=json.dumps(result["updated_active_quests"]))
    emit("game_msg", {"text": result["message"], "type": "info"})
    handle_get_state()


@socketio.on("quest_complete")
def handle_quest_complete(data):
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    qid = data.get("quest_id")

    result = complete_quest(char, qid)
    if not result["success"]:
        emit("game_msg", {"text": result.get("message", ""), "type": "error"})
        return

    new_exp = char["exp"] + result["exp_gain"]
    new_gold = char["gold"] + result["gold_gain"]
    new_contrib = (char["sect_contrib"] or 0) + result["sect_contrib_gain"]

    if result["item_rewards"]:
        inv = get_character_inventory(session["user_id"])
        for iid, cnt in result["item_rewards"].items():
            inv[iid] = inv.get(iid, 0) + cnt
        set_character_inventory(session["user_id"], inv)

    update_character(session["user_id"], exp=new_exp, gold=new_gold,
                     sect_contrib=new_contrib,
                     npc_goodwill=json.dumps(result["updated_goodwill"]),
                     active_quests=json.dumps(result["updated_active_quests"]),
                     completed_quests=json.dumps(result["updated_completed_quests"]))
    emit("game_msg", {"text": result["message"], "type": "heal"})
    emit("game_msg", {"text": result["reward_text"], "type": "shop"})
    handle_get_state()


def _check_quest_progress(char, event_type, key, count=1):
    """检查并更新任务进度"""
    uid = char["user_id"] if "user_id" in char else session.get("user_id")
    changed, updated_quests = check_quest_progress(char, event_type, key, count)
    if changed and uid:
        update_character(uid, active_quests=json.dumps(updated_quests))


# ═══════════════ 拍卖行系统 ═══════════════

import uuid as _uuid

# 拍卖品池：每件拍品有上架概率、稀有度、起拍价范围
AUCTION_POOL = [
    # ── 稀有（高概率上架）──
    {"id": "xuming_dan",     "rarity": "rare", "base_price": (200, 350),   "prob": 0.7, "desc": "恢复200气血"},
    {"id": "juling_dan",     "rarity": "rare", "base_price": (300, 500),   "prob": 0.7, "desc": "获得150修为"},
    {"id": "liliang_fulu2",  "rarity": "rare", "base_price": (400, 600),   "prob": 0.6, "desc": "攻击+5(永久)"},
    {"id": "huti_fulu2",     "rarity": "rare", "base_price": (400, 600),   "prob": 0.6, "desc": "防御+5(永久)"},
    {"id": "qifu_fulu",      "rarity": "rare", "base_price": (300, 500),   "prob": 0.6, "desc": "气血+30(永久)"},
    {"id": "egg_rare",       "rarity": "rare", "base_price": (400, 650),   "prob": 0.6, "desc": "孵化稀有灵宠概率更高"},
    {"id": "pet_feed_good",  "rarity": "rare", "base_price": (120, 200),   "prob": 0.7, "desc": "灵宠经验+50"},
    {"id": "map_rare",       "rarity": "rare", "base_price": (350, 550),   "prob": 0.6, "desc": "二档宝藏"},
    {"id": "jiuzhuan_dan",   "rarity": "rare", "base_price": (500, 800),   "prob": 0.5, "desc": "气血完全恢复"},
    # ── 珍品（中概率上架）──
    {"id": "wudao_dan",      "rarity": "epic", "base_price": (700, 1100),  "prob": 0.4, "desc": "获得400修为"},
    {"id": "pojing_dan",     "rarity": "epic", "base_price": (800, 1200),  "prob": 0.35,"desc": "突破必定成功"},
    {"id": "egg_legend",     "rarity": "epic", "base_price": (1200, 1800), "prob": 0.35,"desc": "必定孵化稀有以上"},
    {"id": "pet_feed_best",  "rarity": "epic", "base_price": (500, 800),   "prob": 0.4, "desc": "灵宠经验+200"},
    {"id": "map_legend",     "rarity": "epic", "base_price": (1000, 1500), "prob": 0.3, "desc": "三档宝藏"},
    # ── 传说（低概率上架）──
    {"id": "wudao_dan",      "rarity": "legend", "base_price": (1500, 2500), "prob": 0.15, "desc": "获得400修为（极品）"},
    {"id": "pojing_dan",     "rarity": "legend", "base_price": (2000, 3500), "prob": 0.12, "desc": "突破必定成功（绝品）"},
    {"id": "egg_legend",     "rarity": "legend", "base_price": (2500, 4000), "prob": 0.10, "desc": "传说灵兽蛋（万年难遇）"},
    {"id": "jiuzhuan_dan",   "rarity": "legend", "base_price": (1800, 3000), "prob": 0.12, "desc": "九转还魂丹（起死回生）"},
]

# 拍卖NPC竞拍者
AUCTION_NPC = {
    "name": "金算盘",
    "title": "天机拍卖行大掌柜",
    "budget": 15000,
    "interest": {
        "rare":  {"chance": 0.5, "max_bids": 2, "max_pct": 1.3},
        "epic":  {"chance": 0.7, "max_bids": 3, "max_pct": 1.5},
        "legend":{"chance": 0.85,"max_bids": 4, "max_pct": 2.0},
    },
    "bid_delay": (3, 12),  # NPC出价延迟（秒）
}

active_auctions = {}       # auction_id -> {...}
auction_npc_state = {"total_spent": 0, "budget": AUCTION_NPC["budget"]}
auction_last_refresh = 0   # 上次刷新时间戳(ms)
AUCTION_REFRESH_INTERVAL = 4 * 3600 * 1000  # 4小时(ms)

def _item_name(item_id):
    """获取物品名称（优先从ITEMS，再从坊市静态列表）"""
    if item_id in ITEMS:
        return ITEMS[item_id]["name"]
    # 坊市特殊物品
    _shop_names = {
        "liliang_fulu2": "高级力量符箓", "huti_fulu2": "高级护体符箓",
        "qifu_fulu": "祈福符箓", "pet_feed_good": "高级灵兽粮",
        "pet_feed_best": "万灵精华",
    }
    return _shop_names.get(item_id, item_id)

def _refresh_auctions():
    """刷新拍卖行：随机上架新拍品"""
    global active_auctions, auction_last_refresh
    now = time.time() * 1000  # ms
    auction_last_refresh = now
    # 移除已结束超过5分钟的拍品
    to_del = [k for k, v in active_auctions.items() if v.get("won") and now - v.get("ends_at", 0) > 300000]
    for k in to_del:
        del active_auctions[k]

    # 随机选取新拍品上架
    import random as _r
    for pool_item in AUCTION_POOL:
        if _r.random() > pool_item["prob"]:
            continue
        # 检查是否已有同类拍品
        if any(a["item_id"] == pool_item["id"] and a["rarity"] == pool_item["rarity"] and not a.get("won") for a in active_auctions.values()):
            continue
        low, high = pool_item["base_price"]
        start_price = _r.randint(low, high)
        min_incr = max(10, start_price // 10)
        aid = _uuid.uuid4().hex[:8]
        duration = _r.randint(90, 180) * 1000  # 90~180秒
        active_auctions[aid] = {
            "auction_id": aid,
            "item_id": pool_item["id"],
            "name": _item_name(pool_item["id"]),
            "desc": pool_item["desc"],
            "rarity": pool_item["rarity"],
            "start_price": start_price,
            "current_price": start_price,
            "min_increment": min_incr,
            "highest_bidder": None,   # "player" / "npc" / None
            "bids_player": 0,
            "bids_npc": 0,
            "ends_at": now + duration,
            "won": False,
            "sold_to_npc": False,
            "created_at": now,
        }
        # NPC延迟出价
        npc_interest = AUCTION_NPC["interest"].get(pool_item["rarity"], {})
        if _r.random() < npc_interest.get("chance", 0.3):
            npc_delay = _r.randint(AUCTION_NPC["bid_delay"][0], AUCTION_NPC["bid_delay"][1])
            active_auctions[aid]["npc_bid_at"] = now + npc_delay * 1000
            active_auctions[aid]["npc_max_bids"] = npc_interest.get("max_bids", 2)
            active_auctions[aid]["npc_max_pct"] = npc_interest.get("max_pct", 1.3)

def _npc_may_bid(auction):
    """NPC决定是否出价"""
    npc = auction_npc_state
    if npc["total_spent"] >= npc["budget"]:
        return False
    if auction.get("won") or auction.get("sold_to_npc"):
        return False
    bids = auction.get("bids_npc", 0)
    if bids >= auction.get("npc_max_bids", 2):
        return False
    max_price = int(auction["start_price"] * auction.get("npc_max_pct", 1.3))
    if auction["current_price"] >= max_price:
        return False
    if npc["budget"] - npc["total_spent"] < auction["current_price"] + auction["min_increment"]:
        return False
    return True

def _npc_do_bid(auction):
    """NPC执行出价"""
    increment = auction["min_increment"] * (1 + random.randint(0, 2))
    new_price = auction["current_price"] + increment
    max_price = int(auction["start_price"] * auction.get("npc_max_pct", 1.3))
    new_price = min(new_price, max_price)
    if new_price <= auction["current_price"]:
        return False
    auction["current_price"] = new_price
    auction["highest_bidder"] = "npc"
    auction["bids_npc"] = auction.get("bids_npc", 0) + 1
    return True

def _process_auction_ticks():
    """后台循环：处理NPC出价、拍卖结束、4小时自动刷新"""
    global auction_last_refresh
    while True:
        socketio.sleep(3)
        now = time.time() * 1000

        # 4小时自动刷新拍品
        if now - auction_last_refresh >= AUCTION_REFRESH_INTERVAL:
            _refresh_auctions()
            socketio.emit("auction_log", {"text": "天机拍卖行新一批宝物上架了！", "type": "shop"}, namespace="/")
            socketio.emit("auction_update", {}, namespace="/")

        changed = False
        for aid, a in list(active_auctions.items()):
            if a.get("won") or a.get("sold_to_npc"):
                continue
            # 检查拍卖是否结束
            if now >= a["ends_at"]:
                if a["highest_bidder"] == "player":
                    # 玩家拍得：扣灵石 + 发放物品
                    uid = a.get("player_user_id")
                    if uid:
                        char = get_character(uid)
                        if char and char["gold"] >= a["current_price"]:
                            update_character(uid, gold=char["gold"] - a["current_price"])
                            inv = get_character_inventory(uid)
                            inv[a["item_id"]] = inv.get(a["item_id"], 0) + 1
                            set_character_inventory(uid, inv)
                            socketio.emit("auction_log", {"text": f"你拍得了【{a['name']}】，扣除 {a['current_price']} 灵石！", "type": "shop"}, namespace="/")
                        elif char:
                            socketio.emit("auction_log", {"text": f"你拍得了【{a['name']}】但灵石不足，拍品流拍！", "type": "error"}, namespace="/")
                    a["won"] = True
                    socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
                elif a["highest_bidder"] == "npc":
                    a["sold_to_npc"] = True
                    auction_npc_state["total_spent"] += a["current_price"]
                    socketio.emit("auction_log", {"text": f"【{a['name']}】被金算盘以{a['current_price']}灵石拍走！", "type": "info"}, namespace="/")
                    socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
                else:
                    # 无人出价，流拍
                    a["won"] = True
                changed = True
                continue
            # NPC延迟出价
            npc_bid_at = a.get("npc_bid_at")
            if npc_bid_at and now >= npc_bid_at and _npc_may_bid(a):
                if _npc_do_bid(a):
                    a["npc_bid_at"] = now + random.randint(5, 15) * 1000  # 下次出价延迟
                    socketio.emit("auction_log", {"text": f"金算盘对【{a['name']}】出价 {a['current_price']} 灵石！", "type": "info"}, namespace="/")
                    socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
                    changed = True
            # 拍卖即将结束时NPC最后一搏
            time_left = a["ends_at"] - now
            if 0 < time_left < 15000 and a["highest_bidder"] == "player" and _npc_may_bid(a):
                if random.random() < 0.6:
                    if _npc_do_bid(a):
                        socketio.emit("auction_log", {"text": f"金算盘在最后关头抢价【{a['name']}】→ {a['current_price']}灵石！", "type": "info"}, namespace="/")
                        socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
                        changed = True


# ═══════════════ 拍卖行Socket事件 ═══════════════

@socketio.on("get_auction")
def handle_get_auction():
    if "user_id" not in session: return
    # 首次打开或拍品为空时初始化
    if not active_auctions:
        _refresh_auctions()
    now = time.time() * 1000
    items = []
    for aid, a in sorted(active_auctions.items(), key=lambda x: x[1].get("created_at", 0)):
        items.append({
            "auction_id": a["auction_id"],
            "item_id": a["item_id"],
            "name": a["name"],
            "desc": a["desc"],
            "rarity": a["rarity"],
            "current_price": a["current_price"],
            "min_increment": a["min_increment"],
            "highest_bidder": a["highest_bidder"],
            "ends_at": a["ends_at"],
            "won": a.get("won", False),
            "sold_to_npc": a.get("sold_to_npc", False),
            "player_won": a.get("won") and a["highest_bidder"] == "player",
        })
    next_refresh = auction_last_refresh + AUCTION_REFRESH_INTERVAL
    emit("auction_list", {"items": items, "next_refresh": next_refresh})

@socketio.on("auction_bid")
def handle_auction_bid(data):
    if "user_id" not in session: return
    touch_activity(session.get("username", ""))
    char = get_character(session["user_id"])
    if not char: return

    aid = data.get("auction_id")
    amount = data.get("amount", 0)
    if not aid or aid not in active_auctions:
        emit("game_msg", {"text": "该拍品已不存在。", "type": "error"})
        return

    a = active_auctions[aid]
    if a.get("won") or a.get("sold_to_npc"):
        emit("game_msg", {"text": "该拍品已成交。", "type": "error"})
        return

    now = time.time() * 1000
    if now >= a["ends_at"]:
        emit("game_msg", {"text": "拍卖已结束。", "type": "error"})
        return

    min_bid = a["current_price"] + a["min_increment"]
    if amount < min_bid:
        emit("game_msg", {"text": f"出价不得低于 {min_bid} 灵石。", "type": "error"})
        return

    if amount > char["gold"]:
        emit("game_msg", {"text": f"灵石不足！你只有 {char['gold']} 灵石。", "type": "error"})
        return

    # 记录出价（不扣灵石，成交时才扣）
    a["current_price"] = amount
    a["highest_bidder"] = "player"
    a["bids_player"] = a.get("bids_player", 0) + 1
    a["player_user_id"] = session["user_id"]  # 记录玩家ID，成交时扣款用

    # 延长拍卖时间（防止最后秒杀）
    time_left = a["ends_at"] - now
    if time_left < 20000:
        a["ends_at"] = now + 20000  # 至少剩余20秒

    # NPC可能加价
    npc_interest = AUCTION_NPC["interest"].get(a["rarity"], {})
    if random.random() < npc_interest.get("chance", 0.3) and _npc_may_bid(a):
        npc_delay = random.randint(AUCTION_NPC["bid_delay"][0], AUCTION_NPC["bid_delay"][1])
        a["npc_bid_at"] = now + npc_delay * 1000

    emit("game_msg", {"text": f"你对【{a['name']}】出价 {amount} 灵石！", "type": "shop"})
    socketio.emit("auction_update", {"auction_id": aid}, namespace="/")
    handle_get_state()


# ═══════════════ 启动 ═══════════════

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("xiantu")

init_db()
logger.info("仙途服务器启动中...")

if __name__ == "__main__":
    socketio.start_background_task(check_afk_loop)
    socketio.start_background_task(_process_auction_ticks)
    logger.info("仙途服务器已就绪，端口 %s", PORT)
    socketio.run(app, host=HOST, port=PORT, debug=False, allow_unsafe_werkzeug=True)
