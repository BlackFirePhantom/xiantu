"""仙途 — 修仙文字在线游戏主程序"""

import random
import hashlib
import secrets
import time
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit

from models import (
    init_db, create_user, get_user, create_character,
    get_character, update_character, get_character_inventory,
    set_character_inventory, get_leaderboard,
)
from game_data import (
    LOCATIONS, MONSTERS, ITEMS, DROP_TABLE, EXP_PER_LEVEL, MAX_LEVEL,
    BREAKTHROUGH_CHANCE, REALMS, SPIRIT_ROOTS, TECHNIQUES, MERIDIANS,
    RECIPES, FORTUNE_EVENTS, SURPRISE_EVENTS, ELEMENT_COUNTER,
    FORGE_RECIPES, FORGE_REALM_BONUS_PER_LV,
    realm_name, spawn_monster, roll_spirit_root, generate_equip, lookup_item,
    IDLE_EXP_PER_SEC, IDLE_MAX_HOURS,
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

online_users = {}
last_activity = {}     # username -> timestamp of last action
afk_players = {}       # username -> timestamp when AFK started
AFK_TIMEOUT = 600      # 10 minutes (seconds) of inactivity -> AFK
AFK_MAX_HOURS = 24     # max AFK accumulation
AFK_INTERVAL = 60      # AFK rewards every 60 seconds

# ═══════════════ 辅助函数 ═══════════════

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
    return hashlib.sha256(password.encode()).hexdigest()

def calc_level_stats(level):
    return {
        "max_hp": 100 + (level - 1) * 15,
        "atk": 10 + (level - 1) * 3,
        "def_stat": 5 + (level - 1) * 2,
    }

def get_full_stats(char):
    base = calc_level_stats(char["level"])
    atk = base["atk"]
    defn = base["def_stat"]
    max_hp = base["max_hp"]

    # 装备加成
    w = lookup_item(char["weapon"]) if char["weapon"] else None
    if w: atk += w.get("atk", 0)
    a = lookup_item(char["armor"]) if char["armor"] else None
    if a: defn += a.get("def", 0)
    ac = lookup_item(char["accessory"]) if char["accessory"] else None
    if ac:
        atk += ac.get("atk", 0)
        defn += ac.get("def", 0)
        max_hp += ac.get("bonus_hp", 0)

    # 功法加成
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    for tid in learned:
        if tid in TECHNIQUES:
            t = TECHNIQUES[tid]
            max_hp += t["bonus_hp"]
            atk += t["bonus_atk"]
            defn += t["bonus_def"]

    # 经脉加成
    opened = json.loads(char["open_meridians"]) if char["open_meridians"] else []
    for mid in opened:
        if mid in MERIDIANS:
            m = MERIDIANS[mid]
            max_hp += m["bonus_hp"]
            atk += m["bonus_atk"]
            defn += m["bonus_def"]

    return {"atk": atk, "def": defn, "max_hp": max_hp}

def get_exp_needed(level):
    if level >= MAX_LEVEL: return "-"
    return EXP_PER_LEVEL[level] if level < len(EXP_PER_LEVEL) else EXP_PER_LEVEL[-1]

def get_cultivation_mult(char):
    """获取修炼速度总倍率（灵根 × 功法）"""
    mult = 1.0
    sr = char["spirit_root"]
    if sr and sr in SPIRIT_ROOTS:
        mult *= SPIRIT_ROOTS[sr]["cultivation_mult"]
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    for tid in learned:
        if tid in TECHNIQUES:
            mult += TECHNIQUES[tid]["bonus_exp_pct"]
    # 饰品修炼加成
    ac = lookup_item(char["accessory"]) if char["accessory"] else None
    if ac:
        mult += ac.get("bonus_exp_pct", 0)
    return mult

def process_offline_cultivation(char):
    """计算离线挂机修为收益，返回 (gain, seconds)"""
    if not char["last_active"]:
        return 0, 0
    try:
        last = datetime.fromisoformat(char["last_active"])
    except (ValueError, TypeError):
        return 0, 0
    elapsed = (datetime.utcnow() - last).total_seconds()
    max_sec = IDLE_MAX_HOURS * 3600
    elapsed = min(elapsed, max_sec)
    if elapsed < 10:
        return 0, 0
    mult = get_cultivation_mult(char)
    gain = int(IDLE_EXP_PER_SEC * elapsed * mult)
    if get_exp_needed(char["level"]) == "-":
        gain = 0
    return max(0, gain), int(elapsed)

def format_duration(seconds):
    if seconds < 60: return f"{seconds}秒"
    if seconds < 3600: return f"{seconds // 60}分钟"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}小时{m}分钟" if m else f"{h}小时"

# 战斗文案
ATTACK_VERBS = [
    "催动灵力，一掌拍向{m}", "祭出飞剑，剑光一闪斩向{m}",
    "凝聚灵力于拳，轰向{m}", "掐动法诀，一道灵光射向{m}",
    "运转功法，灵力化作刀芒劈向{m}",
]
MONSTER_ATTACK_VERBS = [
    "{m}怒吼一声，一爪拍来", "{m}张口喷出一道妖气",
    "{m}浑身妖力暴涨，猛扑过来", "{m}凝聚妖力，化作暗影袭来",
]

def fmt_attack(n): return random.choice(ATTACK_VERBS).format(m=n)
def fmt_monster_attack(n): return random.choice(MONSTER_ATTACK_VERBS).format(m=n)

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
            return render_template("index.html", page="login", success="注册成功，请登录踏入仙途")
        return render_template("index.html", page="register", error="此道号已被他人所用")
    return render_template("index.html", page="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = get_user(username)
        if user and user["password_hash"] == hash_password(password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("game"))
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
    if "username" not in session: return False
    username = session["username"]
    online_users[username] = request.sid
    touch_activity(username)
    emit("system_msg", {"text": f"{username} 踏入了修仙界"}, broadcast=True)

@socketio.on("disconnect")
def handle_disconnect():
    username = session.get("username")
    if username:
        online_users.pop(username, None)
        afk_players.pop(username, None)
        last_activity.pop(username, None)
        socketio.emit("system_msg", {"text": f"{username} 离开了修仙界"}, broadcast=True)


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
            inv_display.append({"id": item_id, "name": item["name"], "count": count, "desc": item.get("desc", "")})

    equip_info = {"weapon": None, "armor": None, "accessory": None}
    w = lookup_item(char["weapon"]) if char["weapon"] else None
    if w: equip_info["weapon"] = {"id": char["weapon"], "name": w["name"], "desc": w.get("desc", "")}
    a = lookup_item(char["armor"]) if char["armor"] else None
    if a: equip_info["armor"] = {"id": char["armor"], "name": a["name"], "desc": a.get("desc", "")}
    ac = lookup_item(char["accessory"]) if char["accessory"] else None
    if ac: equip_info["accessory"] = {"id": char["accessory"], "name": ac["name"], "desc": ac.get("desc", "")}

    connections_display = [{"id": c, "name": LOCATIONS[c]["name"]} for c in loc["connections"] if c in LOCATIONS]

    # 灵根信息
    sr_id = char["spirit_root"]
    sr_info = None
    if sr_id and sr_id in SPIRIT_ROOTS:
        sr = SPIRIT_ROOTS[sr_id]
        sr_info = {"id": sr_id, "name": sr["name"], "desc": sr["desc"], "element": sr["element"]}

    # 功法信息
    learned_tech = []
    for tid in (json.loads(char["techniques"]) if char["techniques"] else []):
        if tid in TECHNIQUES:
            t = TECHNIQUES[tid]
            learned_tech.append({"id": tid, "name": t["name"], "tier": t["tier"]})

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

    socketio.emit("player_moved", {"player": session["username"], "to": target, "to_name": new_loc["name"]}, broadcast=True, include_self=False)

    # 奇遇判定
    char = get_character(session["user_id"])
    check_fortune(char)

    # 突发事件判定（移动类）
    char = get_character(session["user_id"])
    process_surprise(char, "move")

    handle_get_state()


def check_fortune(char):
    """奇遇判定"""
    for event in FORTUNE_EVENTS:
        if random.random() < event["chance"]:
            emit("fortune_event", {
                "title": event["title"],
                "text": event["text"],
                "choices": [{"index": i, "text": c["text"]} for i, c in enumerate(event["choices"])],
                "event_id": event["id"],
            })
            return


def process_surprise(char, trigger):
    """处理突发事件"""
    uid = session["user_id"]
    for evt in SURPRISE_EVENTS:
        if evt["trigger"] != trigger or random.random() >= evt["chance"]:
            continue
        emit("game_msg", {"text": f"【突发】{evt['text']}", "type": "info"})
        eff = evt.get("effect")
        if eff == "extra_fight":
            # 触发一次额外战斗
            handle_fight()
            return
        elif eff == "exp_boost":
            gain = random.randint(*evt["value_range"])
            update_character(uid, exp=char["exp"] + gain)
            emit("game_msg", {"text": f"修为提升 {gain}！", "type": "buff"})
            char["exp"] += gain
        elif eff == "gold_gain":
            gain = random.randint(*evt["value_range"])
            update_character(uid, gold=char["gold"] + gain)
            emit("game_msg", {"text": f"获得 {gain} 灵石。", "type": "shop"})
            char["gold"] += gain
        elif eff == "herb_gain":
            herb = random.choice(evt["herb_pool"])
            count = random.randint(*evt["count_range"])
            inv = get_character_inventory(uid)
            inv[herb] = inv.get(herb, 0) + count
            set_character_inventory(uid, inv)
            emit("game_msg", {"text": f"获得【{ITEMS[herb]['name']}】x{count}！", "type": "shop"})
        elif eff == "heal_partial":
            stats = get_full_stats(char)
            heal = random.randint(*evt["value_range"])
            new_hp = min(char["hp"] + heal, stats["max_hp"])
            update_character(uid, hp=new_hp)
            emit("game_msg", {"text": f"恢复了 {new_hp - char['hp']} 气血。", "type": "heal"})
            char["hp"] = new_hp
        elif eff == "storm":
            stats = get_full_stats(char)
            hp_loss = int(stats["max_hp"] * evt["hp_loss_pct"])
            exp_gain = random.randint(*evt["exp_gain_range"])
            new_hp = max(1, char["hp"] - hp_loss)
            update_character(uid, hp=new_hp, exp=char["exp"] + exp_gain)
            emit("game_msg", {"text": f"损失 {hp_loss} 气血，但修为提升 {exp_gain}。", "type": "info"})
            char["hp"] = new_hp
            char["exp"] += exp_gain
        elif eff == "item_gain":
            inv = get_character_inventory(uid)
            inv[evt["item"]] = inv.get(evt["item"], 0) + evt["count"]
            set_character_inventory(uid, inv)
            emit("game_msg", {"text": f"获得【{ITEMS[evt['item']]['name']}】x{evt['count']}！", "type": "shop"})
        elif eff == "loot_cache":
            inv = get_character_inventory(uid)
            for item_id, count, chance in evt["items"]:
                if random.random() < chance:
                    inv[item_id] = inv.get(item_id, 0) + count
                    emit("game_msg", {"text": f"获得【{ITEMS[item_id]['name']}】x{count}！", "type": "shop"})
            gold_gain = random.randint(*evt["gold_range"])
            set_character_inventory(uid, inv)
            update_character(uid, gold=char["gold"] + gold_gain)
            char["gold"] += gold_gain
        elif eff == "material_gain":
            mat = random.choice(evt["mat_pool"])
            count = random.randint(*evt["count_range"])
            inv = get_character_inventory(uid)
            inv[mat] = inv.get(mat, 0) + count
            set_character_inventory(uid, inv)
            emit("game_msg", {"text": f"获得【{ITEMS[mat]['name']}】x{count}！", "type": "shop"})
        return  # 只触发一个突发事件


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
    process_fortune_outcome(char, outcome)


def _try_learn_technique(char, uid):
    """尝试随机学习一门功法，返回是否成功"""
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    available = [tid for tid, t in TECHNIQUES.items() if tid not in learned and char["level"] >= t["req_realm"]]
    if available:
        chosen = random.choice(available)
        learned.append(chosen)
        update_character(uid, techniques=json.dumps(learned))
        t = TECHNIQUES[chosen]
        emit("game_msg", {"text": f"你领悟了【{t['name']}】（{t['tier']}）！", "type": "buff"})
        return True
    return False

def _give_random_item(uid, pool=None):
    """随机给一个物品，返回item_id"""
    if pool is None:
        pool = [("peiyuan_dan", 0.3), ("huichun_dan", 0.3), ("liliang_fulu", 0.15), ("huti_fulu", 0.15), ("pojing_dan", 0.1)]
    r = random.random()
    cum = 0
    chosen = pool[0][0]
    for item_id, chance in pool:
        cum += chance
        if r < cum:
            chosen = item_id
            break
    inv = get_character_inventory(uid)
    inv[chosen] = inv.get(chosen, 0) + 1
    set_character_inventory(uid, inv)
    emit("game_msg", {"text": f"你获得了一枚【{ITEMS[chosen]['name']}】！", "type": "shop"})
    return chosen

def process_fortune_outcome(char, outcome):
    uid = session["user_id"]
    if outcome == "nothing":
        emit("game_msg", {"text": "你谨慎地选择了离开。", "type": "info"})

    elif outcome == "heal_full":
        stats = get_full_stats(char)
        update_character(uid, hp=stats["max_hp"])
        emit("game_msg", {"text": "你运转功法调息，气血完全恢复，灵台一片清明。", "type": "heal"})

    elif outcome == "reward_random":
        _give_random_item(uid)

    elif outcome == "reward_technique":
        if not _try_learn_technique(char, uid):
            gold_gain = random.randint(50, 150)
            update_character(uid, gold=char["gold"] + gold_gain)
            emit("game_msg", {"text": f"虽未领悟功法，但你感悟颇多，获得 {gold_gain} 灵石。", "type": "shop"})

    elif outcome == "reward_technique_or_item":
        if not _try_learn_technique(char, uid):
            _give_random_item(uid)

    elif outcome == "reward_technique_or_exp":
        if not _try_learn_technique(char, uid):
            gain = random.randint(50, 120)
            update_character(uid, exp=char["exp"] + gain)
            emit("game_msg", {"text": f"虽未领悟功法，但老者的点拨让你感悟颇深，修为提升 {gain}！", "type": "buff"})

    elif outcome == "reward_technique_or_gold":
        if not _try_learn_technique(char, uid):
            gold_gain = random.randint(60, 180)
            update_character(uid, gold=char["gold"] + gold_gain)
            emit("game_msg", {"text": f"此人感激涕零，将全部身家 {gold_gain} 灵石赠予你。", "type": "shop"})

    elif outcome == "reward_exp_small":
        gain = random.randint(15, 40)
        update_character(uid, exp=char["exp"] + gain)
        emit("game_msg", {"text": f"你略有所悟，修为提升 {gain}。", "type": "buff"})

    elif outcome == "reward_exp_big":
        gain = random.randint(40, 100)
        update_character(uid, exp=char["exp"] + gain)
        emit("game_msg", {"text": f"你感悟颇深，灵力涌入丹田，修为提升 {gain}！", "type": "buff"})

    elif outcome == "reward_exp_huge":
        gain = random.randint(100, 300)
        update_character(uid, exp=char["exp"] + gain)
        emit("game_msg", {"text": f"天地法则涌入你的识海，修为暴涨 {gain}！丹田中灵力翻涌不止！", "type": "buff"})

    elif outcome == "reward_exp_big_or_damage":
        if random.random() < 0.5:
            gain = random.randint(40, 100)
            update_character(uid, exp=char["exp"] + gain)
            emit("game_msg", {"text": f"老者目光一闪，一道灵力涌入你的识海——修为提升 {gain}！「不错，有胆识。」", "type": "buff"})
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 6
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            emit("game_msg", {"text": f"老者轻哼一声，一股无形的压力将你震退——你受到 {dmg} 点伤害。「不知天高地厚。」", "type": "error"})

    elif outcome == "reward_exp_huge_or_trap":
        if random.random() < 0.4:
            gain = random.randint(100, 300)
            update_character(uid, exp=char["exp"] + gain)
            emit("game_msg", {"text": f"你成功深入遗迹核心，获得上古大能的残余传承——修为暴涨 {gain}！", "type": "buff"})
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 3
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            emit("game_msg", {"text": f"遗迹中的阵法突然发动！一道灵光击中你——受到 {dmg} 点伤害，你狼狈逃出。", "type": "error"})

    elif outcome == "reward_item_huichun":
        inv = get_character_inventory(uid)
        inv["huichun_dan"] = inv.get("huichun_dan", 0) + 2
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": "你装了两瓶灵泉水，效果堪比【回春丹】。", "type": "shop"})

    elif outcome == "reward_item_peiyuan":
        inv = get_character_inventory(uid)
        inv["peiyuan_dan"] = inv.get("peiyuan_dan", 0) + 1
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": "你获得了一枚散发着清香的【培元丹】！", "type": "shop"})

    elif outcome == "reward_item_peiyuan_or_pojing":
        if random.random() < 0.3:
            inv = get_character_inventory(uid)
            inv["pojing_dan"] = inv.get("pojing_dan", 0) + 1
            set_character_inventory(uid, inv)
            emit("game_msg", {"text": "你以灵力探入石珠，珠中竟封印着一枚【破境丹】！此物价值连城！", "type": "shop"})
        else:
            inv = get_character_inventory(uid)
            inv["peiyuan_dan"] = inv.get("peiyuan_dan", 0) + 2
            set_character_inventory(uid, inv)
            emit("game_msg", {"text": "石珠解封后化作两枚【培元丹】，也算不错。", "type": "shop"})

    elif outcome == "reward_item_multiple":
        inv = get_character_inventory(uid)
        for item_id in random.sample(["huiqi_dan","huichun_dan","peiyuan_dan","lingcao","bingling_cao"], 3):
            inv[item_id] = inv.get(item_id, 0) + 1
        set_character_inventory(uid, inv)
        update_character(uid, gold=char["gold"] - 50)
        emit("game_msg", {"text": "你花了50灵石买了好几样东西，其中混着那枚石珠。收获颇丰。", "type": "shop"})

    elif outcome == "reward_item_or_nothing":
        if random.random() < 0.5:
            _give_random_item(uid, [("peiyuan_dan", 0.4), ("pojing_dan", 0.1), ("juling_dan", 0.3), ("wudao_dan", 0.2)])
        else:
            emit("game_msg", {"text": "你犹豫太久，玉简已被他人拍走。", "type": "error"})

    elif outcome == "reward_item_rare":
        inv = get_character_inventory(uid)
        rare = random.choice(["pojing_dan", "juling_dan", "wudao_dan", "jiuzhuan_dan"])
        inv[rare] = inv.get(rare, 0) + 1
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": f"玉佩灵光一闪，化作一枚【{ITEMS[rare]['name']}】落入你掌中。因果了却，灵台通明。", "type": "shop"})

    elif outcome == "reward_item_rare_or_trap":
        if random.random() < 0.5:
            inv = get_character_inventory(uid)
            rare = random.choice(["wanling_guo","longxian_cao","fengxue_hua"])
            inv[rare] = inv.get(rare, 0) + 2
            set_character_inventory(uid, inv)
            emit("game_msg", {"text": f"鸟卵中蕴含着浓郁灵气，化作两株【{ITEMS[rare]['name']}】。", "type": "shop"})
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 4
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            emit("game_msg", {"text": f"你刚伸手，青鸾暴怒之下一爪拍来！受到 {dmg} 点伤害，你仓皇逃走。", "type": "error"})

    elif outcome == "reward_item_scroll":
        inv = get_character_inventory(uid)
        scroll = random.choice(["liliang_fulu","huti_fulu","qifu_fulu"])
        inv[scroll] = inv.get(scroll, 0) + 1
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": f"你拓印了壁画内容，制成一枚【{ITEMS[scroll]['name']}】。", "type": "shop"})

    elif outcome == "reward_herbs":
        inv = get_character_inventory(uid)
        herbs = random.choice(["lingcao", "bingling_cao", "huoling_hua"])
        count = random.randint(2, 4)
        inv[herbs] = inv.get(herbs, 0) + count
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": f"你悄悄采摘了 {count} 株【{ITEMS[herbs]['name']}】，巨蟒并未察觉。", "type": "shop"})

    elif outcome == "reward_herbs_rare":
        inv = get_character_inventory(uid)
        rare = random.choice(["wanling_guo","longxian_cao","fengxue_hua"])
        inv[rare] = inv.get(rare, 0) + 1
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": f"你以一枚回气丹换取巨蟒的信任，它竟从谷底叼来一株【{ITEMS[rare]['name']}】赠你。", "type": "shop"})

    elif outcome == "reward_herbs_poison_or_fight":
        if random.random() < 0.6:
            inv = get_character_inventory(uid)
            inv["dueling_teng"] = inv.get("dueling_teng", 0) + 3
            inv["bingling_cao"] = inv.get("bingling_cao", 0) + 1
            set_character_inventory(uid, inv)
            emit("game_msg", {"text": "你屏息潜入，成功采得毒灵藤x3和冰灵草x1，迅速撤离。", "type": "shop"})
        else:
            emit("game_msg", {"text": "你刚靠近毒灵藤，沼泽中一头毒蟒猛然窜出！", "type": "error"})
            handle_fight()

    elif outcome == "reward_gold_bad" or outcome == "reward_gold_small":
        gain = random.randint(20, 60)
        update_character(uid, gold=char["gold"] + gain)
        emit("game_msg", {"text": f"你获得 {gain} 灵石。", "type": "shop"})

    elif outcome == "reward_gold_big_or_trap":
        if random.random() < 0.4:
            gold_gain = random.randint(100, 300)
            inv = get_character_inventory(uid)
            for mid in random.sample(["yaodan","yaogu","yaopimo"], 2):
                inv[mid] = inv.get(mid, 0) + 2
            set_character_inventory(uid, inv)
            update_character(uid, gold=char["gold"] + gold_gain)
            emit("game_msg", {"text": f"储物戒指中竟有 {gold_gain} 灵石和大量妖兽材料！你发财了！", "type": "shop"})
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 3
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            emit("game_msg", {"text": f"你刚触碰飞剑，洞府中沉寂万年的守护阵法轰然发动！一道灵光击中你——受到 {dmg} 点伤害。", "type": "error"})

    elif outcome == "reward_materials":
        inv = get_character_inventory(uid)
        for mid in random.sample(["hantie_kuang","xuanjin_shi","yaodan"], 2):
            inv[mid] = inv.get(mid, 0) + random.randint(1, 3)
        set_character_inventory(uid, inv)
        emit("game_msg", {"text": "你小心收集了陨落之地散落的矿石和材料。", "type": "shop"})

    elif outcome == "reward_materials_or_trap":
        if random.random() < 0.5:
            inv = get_character_inventory(uid)
            for mid in random.sample(["xuanjin_shi","tianwai_yuntie","yaodan"], 2):
                inv[mid] = inv.get(mid, 0) + random.randint(1, 2)
            set_character_inventory(uid, inv)
            emit("game_msg", {"text": "你破解了阵法，搜刮了洞府中的矿石和材料。", "type": "shop"})
        else:
            stats = get_full_stats(char)
            dmg = stats["max_hp"] // 4
            new_hp = max(1, char["hp"] - dmg)
            update_character(uid, hp=new_hp)
            emit("game_msg", {"text": f"你触碰物品的瞬间，噬灵阵轰然发动！受到 {dmg} 点伤害，你拼命逃出。", "type": "error"})

    elif outcome == "reward_materials_rare":
        inv = get_character_inventory(uid)
        inv["tianwai_yuntie"] = inv.get("tianwai_yuntie", 0) + 2
        inv["zijin_kuang"] = inv.get("zijin_kuang", 0) + 1
        set_character_inventory(uid, inv)
        update_character(uid, exp=char["exp"] + random.randint(30, 80))
        emit("game_msg", {"text": "你第一个赶到陨落之地，拾得天外陨铁x2、紫金矿x1，混沌之气令修为精进！", "type": "shop"})

    elif outcome == "trap_damage":
        stats = get_full_stats(char)
        dmg = stats["max_hp"] // 4
        new_hp = max(1, char["hp"] - dmg)
        update_character(uid, hp=new_hp)
        emit("game_msg", {"text": f"你强行破阵，受到 {dmg} 点伤害，总算逃出生天。", "type": "error"})

    elif outcome == "trap_damage_big":
        stats = get_full_stats(char)
        dmg = stats["max_hp"] // 3
        new_hp = max(1, char["hp"] - dmg)
        update_character(uid, hp=new_hp)
        emit("game_msg", {"text": f"丹药入喉，化作一股灼热的毒气侵蚀经脉——受到 {dmg} 点伤害！你猛然惊醒，心魔消散。", "type": "error"})

    elif outcome == "trap_pay":
        cost = min(char["gold"], random.randint(20, 80))
        update_character(uid, gold=char["gold"] - cost)
        emit("game_msg", {"text": f"你丢下 {cost} 灵石，趁机脱身。", "type": "error"})

    elif outcome == "fight_bandit" or outcome == "fight_demon_boss":
        handle_fight()

    else:
        emit("game_msg", {"text": "你平静地离开了。", "type": "info"})

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
        exp_gain = monster["exp"]
        gold_gain = monster["gold"] + random.randint(0, monster["gold"] // 2)
        log.append(f"斗法胜利！修为提升 {exp_gain}，获得 {gold_gain} 灵石。")

        drops = []
        if monster_id in DROP_TABLE:
            for item_id, chance in DROP_TABLE[monster_id]:
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

        update_character(session["user_id"], hp=player_hp, exp=char["exp"] + exp_gain, gold=char["gold"] + gold_gain, kills=char["kills"] + 1)
    else:
        gold_lost = char["gold"] // 5
        log.append("你体内灵力耗尽，不敌妖兽……陨落于此。")
        log.append(f"损失 {gold_lost} 灵石，元神被传送回青云镇疗伤。")
        update_character(session["user_id"], hp=max_hp // 2, gold=char["gold"] - gold_lost, deaths=char["deaths"] + 1, location="qingyun_town")

    emit("fight_log", {"log": log, "won": won})
    handle_get_state()


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
    update_character(session["user_id"], hp=stats["max_hp"])
    msgs = [
        "你盘膝而坐，运转功法，天地灵气缓缓涌入体内……气血完全恢复。",
        "你闭目凝神，丹田中的灵力缓缓流转，伤势痊愈，气血充盈。",
        "你静心打坐，体悟天地大道，灵台清明，气血恢复如初。",
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

    emit("game_msg", {"text": "你盘膝坐下，运转功法，尝试突破境界……", "type": "info"})
    if random.random() < chance:
        new_lv = cur_lv + 1
        new_stats = calc_level_stats(new_lv)
        update_character(session["user_id"], level=new_lv, max_hp=new_stats["max_hp"], atk=new_stats["atk"], def_stat=new_stats["def_stat"], hp=new_stats["max_hp"])
        new_realm = realm_name(new_lv)
        if pill_msg: emit("game_msg", {"text": pill_msg, "type": "buff"})
        emit("game_msg", {"text": f"体内灵力暴涌，丹田剧烈震动——突破成功！你已迈入{new_realm}！", "type": "heal"})
        socketio.emit("system_msg", {"text": f"天道感应：{session['username']} 突破至 {new_realm}，引发天地异象！"}, broadcast=True)
    else:
        lost_exp = int(needed * 0.3)
        hp_loss = char["hp"] // 3
        update_character(session["user_id"], exp=max(0, char["exp"] - lost_exp), hp=max(1, char["hp"] - hp_loss))
        emit("game_msg", {"text": f"灵力逆行，经脉受损……突破失败！损失 {lost_exp} 修为。", "type": "error"})
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
    if tid in learned:
        emit("game_msg", {"text": f"你已经领悟了【{t['name']}】。", "type": "error"})
        return
    if char["level"] < t["req_realm"]:
        emit("game_msg", {"text": f"境界不足，需要{realm_name(t['req_realm'])}才能领悟。", "type": "error"})
        return
    cost = t["req_realm"] * 50
    if char["gold"] < cost:
        emit("game_msg", {"text": f"参悟功法需要 {cost} 灵石，灵石不足。", "type": "error"})
        return
    learned.append(tid)
    update_character(session["user_id"], techniques=json.dumps(learned), gold=char["gold"] - cost)
    emit("game_msg", {"text": f"你耗费 {cost} 灵石，潜心参悟，终于领悟了【{t['name']}】（{t['tier']}）！", "type": "buff"})
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
    item = ITEMS[item_id]
    if item["type"] == "material":
        emit("game_msg", {"text": "灵草是炼丹材料，不可直接使用。", "type": "info"})
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
    available = []
    for tid, t in TECHNIQUES.items():
        if tid not in learned:
            cost = t["req_realm"] * 50
            available.append({"id": tid, "name": t["name"], "tier": t["tier"], "desc": t["desc"],
                              "req_realm": realm_name(t["req_realm"]), "cost": cost,
                              "unlockable": char["level"] >= t["req_realm"] and char["gold"] >= cost})
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


# ═══════════════ 启动 ═══════════════

init_db()

if __name__ == "__main__":
    socketio.start_background_task(check_afk_loop)
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
