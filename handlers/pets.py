"""宠物孵化、培养与出战相关的 Socket 事件处理器。"""

import json
import uuid
from flask import session
from flask_socketio import emit

from game_state import (
    get_cached_character as get_character,
    update_cached_character as update_character,
    get_character_inventory_cached as get_character_inventory,
    set_character_inventory_cached as set_character_inventory
)
from game_data import (
    PET_SPECIES, PET_MAX_LEVEL,
    hatch_egg, get_pet_stats, get_pet_exp_needed, lookup_item
)



def get_pet_display_info(char):
    """获取角色所有灵宠的展示信息，供 base.py / get_state 调用"""
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

def do_hatch_egg(data):
    """执行孵蛋，供 items.py 的 use_item 触发"""
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

    pet_uuid = str(uuid.uuid4())[:8]
    new_pet = {"id": pet_uuid, "species_id": species_id, "level": 1, "exp": 0}

    pets = json.loads(char["pets"]) if char["pets"] else []
    pets.append(new_pet)
    update_character(session["user_id"], pets=json.dumps(pets))

    rarity_names = {"common": "普通", "rare": "稀有", "legend": "传说"}
    emit("game_msg", {
        "text": f"你将灵力注入灵兽蛋，蛋壳裂开，一只【{species['name']}】（{rarity_names[species['rarity']]}）破壳而出！它用小脑袋蹭了蹭你的手心。",
        "type": "heal",
    })
    from handlers.base import do_get_state
    do_get_state(session["user_id"])

def register_pets_handlers(socketio):
    @socketio.on("hatch_egg")
    def handle_hatch_egg(data):
        do_hatch_egg(data)

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
        from handlers.base import do_get_state
        do_get_state(session["user_id"])

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
        from handlers.base import do_get_state
        do_get_state(session["user_id"])

    @socketio.on("deactivate_pet")
    def handle_deactivate_pet():
        if "user_id" not in session: return
        char = get_character(session["user_id"])
        if not char: return
        update_character(session["user_id"], active_pet=None)
        emit("game_msg", {"text": "你收回了出战灵宠。", "type": "equip"})
        from handlers.base import do_get_state
        do_get_state(session["user_id"])
