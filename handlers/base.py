"""基础连接与通用状态的 Socket 事件处理器。"""

from datetime import datetime, timezone
from flask import session, request
from flask_socketio import emit

import game_state
from models import get_leaderboard, get_secret_realm_combat_state
from game_state import (
    get_cached_character as get_character,
    update_cached_character as update_character,
    get_character_inventory_cached as get_character_inventory,
    set_character_inventory_cached as set_character_inventory,
)
from game_data import ITEMS, realm_name
from game.utils import format_duration, get_full_stats, week_id
from game.cultivation import process_offline_cultivation
from services.player_state import build_player_state

def register_base_handlers(socketio):
    @socketio.on("connect")
    def handle_connect():
        if "username" not in session:
            return False
        username = session["username"]
        game_state.online_users[username] = request.sid
        game_state.touch_activity(username)
        emit("system_msg", {"text": f"{username} 踏入了修仙界"}, broadcast=True, namespace="/")

    @socketio.on("disconnect")
    def handle_disconnect(reason=None):
        username = session.get("username")
        user_id = session.get("user_id")
        if username:
            game_state.online_users.pop(username, None)
            game_state.afk_players.pop(username, None)
            game_state.last_activity.pop(username, None)
            emit("system_msg", {"text": f"{username} 离开了修仙界"}, broadcast=True, namespace="/")
        if user_id:
            # 清理可能残留的战斗状态，持久化当前战斗 HP（防止免费满血逃脱）
            with game_state.combat_lock:
                combat = game_state.active_combats.pop(user_id, None)
            if combat:
                update_character(user_id, hp=combat["player_hp"])
            game_state.save_cached_character(user_id)

    @socketio.on("get_state")
    def handle_get_state():
        if "user_id" not in session: return
        game_state.touch_activity(session.get("username", ""))
        do_get_state(session["user_id"])

    @socketio.on("chat")
    def handle_chat(data):
        if "username" not in session: return
        game_state.touch_activity(session.get("username", ""))
        text = data.get("text", "").strip()
        if not text or len(text) > 200: return
        emit("chat_msg", {"from": session["username"], "text": text}, broadcast=True)

    @socketio.on("get_leaderboard")
    def handle_leaderboard():
        rows = get_leaderboard()
        lb = [{"name": r["name"], "level": r["level"], "realm": realm_name(r["level"]), "exp": r["exp"], "kills": r["kills"]} for r in rows]
        emit("leaderboard", {"data": lb})

def do_get_state(user_id):
    char = get_character(user_id)
    if not char:
        emit("need_create")
        return

    # 处理离线挂机（修为 + 材料掉落 + 安全区回血，与在线 AFK 路径一致）
    reward = process_offline_cultivation(char)
    # 秘境回合尚未结束时，不能利用安全区的离线回血刷新战斗生命值。
    # 结算（死亡或击杀首领）会自动清除该回合状态，之后恢复正常回血。
    if get_secret_realm_combat_state(user_id, week_id()):
        reward["heal_to_full"] = False
    if reward["exp"] > 0 or reward["drops"] or reward["heal_to_full"]:
        now_iso = datetime.now(timezone.utc).isoformat()
        updates = {"last_active": now_iso}
        if reward["exp"] > 0:
            updates["exp"] = char["exp"] + reward["exp"]
        if reward["heal_to_full"]:
            stats = get_full_stats(char)
            updates["hp"] = stats["max_hp"]
        update_character(user_id, **updates)
        if reward["drops"]:
            inv = get_character_inventory(user_id)
            for item_id in reward["drops"]:
                inv[item_id] = inv.get(item_id, 0) + 1
            set_character_inventory(user_id, inv)
        char = get_character(user_id)
        msg = f"你闭关修炼了 {format_duration(reward['elapsed'])}，修为增长 {reward['exp']}。"
        if reward["drops"]:
            drop_names = "、".join(ITEMS[d]["name"] for d in reward["drops"] if d in ITEMS)
            if drop_names:
                msg += f" 另获材料：{drop_names}。"
        if reward["heal_to_full"]:
            msg += " 安全区灵气充沛，气血已恢复满值。"
        emit("game_msg", {"text": msg, "type": "heal"})
    else:
        update_character(user_id, last_active=datetime.now(timezone.utc).isoformat())

    inv = get_character_inventory(user_id)
    emit("game_state", build_player_state(
        char,
        inv,
        online_count=len(game_state.online_users),
        is_afk=session.get("username", "") in game_state.afk_players,
    ))
