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

from game_state import online_users, last_activity, afk_players, touch_activity

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


# ═══════════════ WebSocket 处理器初始化 ═══════════════
import game_state
from handlers import init_handlers
from handlers.auction import _process_auction_ticks

# 将拍卖配置注入到全局共享状态中
game_state.AUCTION_POOL = AUCTION_POOL
game_state.auction_npc_state = {"total_spent": 0, "budget": AUCTION_NPC["budget"]}

# 注册所有解耦后的 Socket 事件
init_handlers(socketio)

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
