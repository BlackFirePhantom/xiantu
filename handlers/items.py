"""道具使用、卸载法宝、坊市购买、炼丹、炼器（锻造）相关的 Socket 事件处理器。"""

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
from game_data import (
    LOCATIONS, ITEMS, RECIPES, FORGE_RECIPES, MONSTERS, DROP_TABLE,
    MAP_MONSTER_DROPS, PET_EGG_MONSTER_DROPS, LOCATION_UNIQUE_DROPS,
    FORGE_REALM_BONUS_PER_LV, realm_name, generate_equip, lookup_item
)
from game.utils import get_full_stats

# 导入其它 Handler 提供的功能
from handlers.base import do_get_state
# 延迟导入宠物和秘境的业务逻辑，避免可能因后续文件未建好的编译错误或循环依赖
# 将在 handle_use_item 内部进行 import 即可，确保单向调用

# 坊市可购买物品列表（用于物品来源展示）
_SHOP_ITEMS = [
    "huiqi_dan", "huichun_dan", "peiyuan_dan", "dingdan",
    "liliang_fulu", "huti_fulu", "tiemu_sword", "cloth_robe",
    "qingyu_peidai", "tongqian_hufu", "egg_common", "pet_feed",
]


def _apply_consumable(char, item, item_id, inv, user_id):
    """处理消耗品使用效果。

    扣减物品并更新角色属性，返回 (消息文本, 消息类型) 元组。
    若物品效果不被识别则返回 None。
    """
    effect = item["effect"]

    # 扣减物品（所有消耗品共用）
    inv[item_id] -= 1
    if inv[item_id] <= 0: del inv[item_id]
    set_character_inventory(user_id, inv)

    if effect == "heal":
        stats = get_full_stats(char)
        new_hp = min(char["hp"] + item["value"], stats["max_hp"])
        healed = new_hp - char["hp"]
        update_character(user_id, hp=new_hp)
        return f"你服下【{item['name']}】，药力化开，恢复了 {healed} 气血。", "heal"

    if effect == "heal_full":
        stats = get_full_stats(char)
        update_character(user_id, hp=stats["max_hp"])
        return f"你服下【{item['name']}】，灵丹妙药，气血完全恢复！", "heal"

    if effect == "exp":
        update_character(user_id, exp=char["exp"] + item["value"])
        return f"你服下【{item['name']}】，灵力涌入丹田，修为提升 {item['value']}。", "buff"

    if effect == "breakthrough":
        update_character(user_id, has_breakthrough_pill=1)
        return f"你收好【{item['name']}】，下次突破时将自动使用。", "buff"

    if effect == "combat_buff":
        update_character(user_id, combat_buff=item["value"])
        return f"你服下【{item['name']}】，灵力暴涨，下次战斗伤害提升{item['value']}%！", "buff"

    if effect == "hp_up":
        update_character(user_id, max_hp=char["max_hp"] + item["value"], hp=char["hp"] + item["value"])
        return f"你催动【{item['name']}】，符箓化作灵光涌入丹田，气血上限永久 +{item['value']}！", "buff"

    if effect == "atk_up":
        update_character(user_id, atk=char["atk"] + item["value"])
        return f"你催动【{item['name']}】，符箓化作灵光融入体内，攻击永久 +{item['value']}！", "buff"

    if effect == "def_up":
        update_character(user_id, def_stat=char["def_stat"] + item["value"])
        return f"你催动【{item['name']}】，符箓化作灵光护体，防御永久 +{item['value']}！", "buff"

    return None


def _gather_item_sources(item_id):
    """搜集物品的所有来源描述，返回字符串列表。"""
    item = lookup_item(item_id)
    sources = []

    if item_id in _SHOP_ITEMS:
        sources.append("坊市购买")

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

    loc_names = []
    for loc_id, drops in LOCATION_UNIQUE_DROPS.items():
        for did, _ in drops:
            if did == item_id:
                loc_names.append(LOCATIONS.get(loc_id, {}).get("name", loc_id))
    if loc_names:
        sources.append(f"独有产出（{', '.join(loc_names)}）")

    for rid, r in RECIPES.items():
        if r.get("result") == item_id:
            sources.append(f"炼丹获得（{r['name']}）")
            break
    for rid, r in FORGE_RECIPES.items():
        if r.get("result_slot"):
            sources.append("炼器锻造")
            break

    if item_id in [p["id"] for p in game_state.AUCTION_POOL]:
        sources.append("拍卖行竞拍")

    if item:
        if item.get("type") == "treasure_map":
            sources.append("使用后探索宝藏")
        if item.get("type") == "map_upgrade":
            sources.append("高级怪物掉落")
        if item.get("type") == "technique_fragment":
            sources.append("宝藏探索获得")

    if not sources:
        sources.append("探索世界获取")

    return sources

def register_items_handlers(socketio):
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
        do_get_state(session["user_id"])

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

        do_get_state(session["user_id"])

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
            from handlers.pets import do_hatch_egg
            do_hatch_egg({"item": item_id})
            return
        if item["type"] == "pet_food":
            emit("game_msg", {"text": "灵兽饲料请在灵宠面板中喂养。", "type": "info"})
            return
        if item["type"] == "treasure_map":
            from handlers.adventure import do_use_map
            do_use_map({"item": item_id})
            return
        if item["type"] == "map_upgrade":
            emit("game_msg", {"text": "寻宝罗盘请在储物袋中对藏宝图使用。", "type": "info"})
            return
        if item["type"] == "technique_fragment":
            from handlers.adventure import do_combine_fragments
            do_combine_fragments({"group": item["fragment_group"]})
            return

        if item["type"] == "consumable":
            result = _apply_consumable(char, item, item_id, inv, session["user_id"])
            if result:
                msg, msg_type = result
                emit("game_msg", {"text": msg, "type": msg_type})
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
        do_get_state(session["user_id"])

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
        do_get_state(session["user_id"])

    @socketio.on("item_detail")
    def handle_item_detail(data):
        if "user_id" not in session: return
        item_id = data.get("item")
        if not item_id: return
        item = lookup_item(item_id)
        if not item: return

        sources = _gather_item_sources(item_id)

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
        do_get_state(session["user_id"])
