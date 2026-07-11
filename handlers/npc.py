"""NPC 互动与任务进度相关的 Socket 事件处理器。"""

import json
from flask import session
from flask_socketio import emit

from game_state import (
    get_cached_character as get_character,
    update_cached_character as update_character,
    get_character_inventory_cached as get_character_inventory,
    set_character_inventory_cached as set_character_inventory
)
from game.npc import (
    interact_with_npc, give_npc_gift, accept_quest, complete_quest, check_quest_progress
)

# 导入其它 Handler 提供的功能
from handlers.base import do_get_state

def _check_quest_progress(char, event_type, key, count=1):
    """检查并更新任务进度（供其它模块如 combat 调用，实现单向依赖）"""
    uid = char["user_id"] if "user_id" in char else session.get("user_id")
    changed, updated_quests = check_quest_progress(char, event_type, key, count)
    if changed and uid:
        update_character(uid, active_quests=json.dumps(updated_quests))

def register_npc_handlers(socketio):
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
        do_get_state(session["user_id"])

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
        do_get_state(session["user_id"])

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
        do_get_state(session["user_id"])
