"""移动与奇遇相关的 Socket 事件处理器。"""

import json
import random
from flask import session
from flask_socketio import emit

import game_state
from game_state import (
    get_cached_character as get_character,
    update_cached_character as update_character,
    get_character_inventory_cached as get_character_inventory,
    set_character_inventory_cached as set_character_inventory
)
from game_data import LOCATIONS, ITEMS, FORTUNE_EVENTS
from game.events import check_fortune, process_surprise, process_fortune_outcome
from game.npc import check_quest_progress

# 导入其它 Handler 的业务逻辑函数（单向依赖）
from handlers.base import do_get_state
from handlers.combat import do_fight

def _apply_surprise_effect(char, surprise):
    """应用突发事件效果"""
    uid = session["user_id"]
    action = surprise.get("action")
    if action == "extra_fight":
        do_fight()
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

def register_gameplay_handlers(socketio):
    @socketio.on("move")
    def handle_move(data):
        if "user_id" not in session: return
        game_state.touch_activity(session.get("username", ""))
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

        do_get_state(session["user_id"])

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
            do_fight()
        do_get_state(session["user_id"])
