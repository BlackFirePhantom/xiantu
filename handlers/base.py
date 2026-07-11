"""基础连接与通用状态的 Socket 事件处理器。"""

import json
from datetime import datetime
from flask import session, request
from flask_socketio import emit

import game_state
from models import get_leaderboard
from game_state import (
    get_cached_character as get_character,
    update_cached_character as update_character,
    get_character_inventory_cached as get_character_inventory
)
from game_data import (
    LOCATIONS, SPIRIT_ROOTS, TECHNIQUES, MERIDIANS,
    realm_name, lookup_item, TECHNIQUE_MAX_PROFICIENCY
)
from game.utils import (
    format_duration, get_full_stats, get_exp_needed, get_cultivation_mult,
    get_proficiency
)
from game.cultivation import process_offline_cultivation
from game.npc import get_npc_info_for_location, get_quest_info, get_sect_info
from handlers.pets import get_pet_display_info

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
            game_state.save_cached_character(user_id)

    @socketio.on("get_state")
    def handle_get_state():
        if "user_id" not in session: return
        game_state.touch_activity(session.get("username", ""))
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
            "online_count": len(game_state.online_users),
            "is_afk": session.get("username", "") in game_state.afk_players,
        })

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
