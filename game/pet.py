"""灵宠系统逻辑"""

import random
import json
import uuid
from game_data import (
    PET_SPECIES, PET_EGG_TIERS, PET_BATTLE_RATIO, PET_EXP_PER_LEVEL, PET_MAX_LEVEL,
    ITEMS, lookup_item, hatch_egg, get_pet_stats, get_pet_exp_needed,
)


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


def hatch_pet_egg(char, inv, item_id):
    """孵化灵兽蛋，返回结果 dict"""
    item = lookup_item(item_id)
    if not item or item.get("type") != "pet_egg":
        return {"success": False, "message": "这不是灵兽蛋。"}

    if inv.get(item_id, 0) <= 0:
        return {"success": False, "message": "你没有这枚灵兽蛋。"}

    inv[item_id] -= 1
    if inv[item_id] <= 0:
        del inv[item_id]

    egg_tier = item["egg_tier"]
    species_id, species = hatch_egg(egg_tier)

    pet_id = str(uuid.uuid4())[:8]
    new_pet = {"id": pet_id, "species_id": species_id, "level": 1, "exp": 0}

    pets = json.loads(char["pets"]) if char["pets"] else []
    pets.append(new_pet)

    rarity_names = {"common": "普通", "rare": "稀有", "legend": "传说"}
    message = (
        f"你将灵力注入灵兽蛋，蛋壳裂开，一只【{species['name']}】"
        f"（{rarity_names[species['rarity']]}）破壳而出！"
        f"它用小脑袋蹭了蹭你的手心。"
    )

    return {"success": True, "message": message, "updated_inv": inv, "updated_pets": pets}


def feed_pet(char, inv, pet_id, item_id):
    """喂养灵宠，返回结果 dict"""
    item = lookup_item(item_id)
    if not item or item.get("type") != "pet_food":
        return {"success": False, "message": "这不是灵宠食物。"}

    if inv.get(item_id, 0) <= 0:
        return {"success": False, "message": "你没有这个食物。"}

    pets = json.loads(char["pets"]) if char["pets"] else []
    target_pet = None
    for pet in pets:
        if pet["id"] == pet_id:
            target_pet = pet
            break
    if not target_pet:
        return {"success": False, "message": "未找到该灵宠。"}

    if target_pet["level"] >= PET_MAX_LEVEL:
        return {"success": False, "message": "灵宠已达最高等级。"}

    inv[item_id] -= 1
    if inv[item_id] <= 0:
        del inv[item_id]

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

    message = f"你喂了【{species.get('name', '灵宠')}】一份{item['name']}，成长经验+{item['pet_exp']}。"
    return {
        "success": True, "message": message, "level_up_msgs": level_up_msgs,
        "updated_inv": inv, "updated_pets": pets,
    }
