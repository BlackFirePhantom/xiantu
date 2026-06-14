"""
crafting.py - 炼丹与锻造的纯业务逻辑
从 app.py 中提取，不依赖 Flask / SocketIO。
"""
import random

from game_data import (
    RECIPES,
    FORGE_RECIPES,
    FORGE_REALM_BONUS_PER_LV,
    ITEMS,
    generate_equip,
    realm_name,
)


# ═══════════════ 炼丹 ═══════════════

def try_refine_pill(recipe_id: str, char: dict, inv: dict,
                    recipes: dict = None, items: dict = None) -> dict:
    """
    校验并执行炼丹操作。

    参数:
        recipe_id: 配方 id（RECIPES 中的 key）
        char:      角色字典（需含 level）
        inv:       背包字典（item_id -> count）
        recipes:   配方表，默认 RECIPES
        items:     物品表，默认 ITEMS

    返回:
        {"success": bool, "message": str, "updated_inv": dict}
    """
    recipes = recipes or RECIPES
    items = items or ITEMS

    if not recipe_id or recipe_id not in recipes:
        return {"success": False, "message": "配方不存在。", "updated_inv": inv}

    recipe = recipes[recipe_id]

    # 境界检查
    if char["level"] < recipe["req_realm"]:
        return {
            "success": False,
            "message": f"境界不足，需要{realm_name(recipe['req_realm'])}才能炼制。",
            "updated_inv": inv,
        }

    # 材料检查
    for mat, count in recipe["ingredients"].items():
        if inv.get(mat, 0) < count:
            return {
                "success": False,
                "message": f"材料不足！需要{items[mat]['name']} x{count}。",
                "updated_inv": inv,
            }

    # 扣除材料
    for mat, count in recipe["ingredients"].items():
        inv[mat] -= count
        if inv[mat] <= 0:
            del inv[mat]

    # 产出
    output = recipe["output"]
    inv[output] = inv.get(output, 0) + recipe["output_count"]

    return {
        "success": True,
        "message": f"你将灵草投入丹炉，运转灵力催动丹火……丹成！获得【{items[output]['name']}】x{recipe['output_count']}！",
        "updated_inv": inv,
    }


# ═══════════════ 锻造 ═══════════════

def try_forge(recipe_id: str, char: dict, inv: dict,
              forge_recipes: dict = None, forge_realm_bonus: float = None,
              items: dict = None) -> dict:
    """
    校验并执行锻造操作。

    参数:
        recipe_id:       配方 id（FORGE_RECIPES 中的 key）
        char:            角色字典（需含 level）
        inv:             背包字典（item_id -> count）
        forge_recipes:   锻造配方表，默认 FORGE_RECIPES
        forge_realm_bonus: 每级境界加成，默认 FORGE_REALM_BONUS_PER_LV
        items:           物品表，默认 ITEMS

    返回:
        {
            "success": bool,
            "log": [str],
            "updated_inv": dict,
            "item_id": str | None,       # 成功时为装备 id
            "item_data": dict | None,     # 成功时为装备数据
        }
    """
    forge_recipes = forge_recipes or FORGE_RECIPES
    forge_realm_bonus = forge_realm_bonus if forge_realm_bonus is not None else FORGE_REALM_BONUS_PER_LV
    items = items or ITEMS

    if not recipe_id or recipe_id not in forge_recipes:
        return {
            "success": False, "log": ["配方不存在。"],
            "updated_inv": inv, "item_id": None, "item_data": None,
        }

    recipe = forge_recipes[recipe_id]

    # 境界检查
    if char["level"] < recipe["req_realm"]:
        return {
            "success": False,
            "log": [f"境界不足，需要{realm_name(recipe['req_realm'])}才能锻造。"],
            "updated_inv": inv, "item_id": None, "item_data": None,
        }

    # 材料检查
    for mat, count in recipe["ingredients"].items():
        if inv.get(mat, 0) < count:
            return {
                "success": False,
                "log": [f"材料不足！需要{items[mat]['name']} x{count}。"],
                "updated_inv": inv, "item_id": None, "item_data": None,
            }

    # 扣除材料
    for mat, count in recipe["ingredients"].items():
        inv[mat] -= count
        if inv[mat] <= 0:
            del inv[mat]

    # 计算成功率
    base_rate = recipe["success_rate"]
    realm_bonus = max(0, char["level"] - recipe["req_realm"]) * forge_realm_bonus
    final_rate = min(0.99, base_rate + realm_bonus)

    mat_names = "、".join([f"{items[m]['name']}x{c}" for m, c in recipe["ingredients"].items()])
    log_lines = [f"你将{mat_names}投入器炉，运转灵力催动炉火……"]

    item_id = None
    item_data = None

    if random.random() < final_rate:
        item_id, item_data = generate_equip(recipe["slot"], recipe["tier"])
        inv[item_id] = inv.get(item_id, 0) + 1
        pct = int(final_rate * 100)
        log_lines.append(
            f"炉中光芒大放！锻造成功（{pct}%）"
            f"——获得【{item_data['name']}】！{item_data['grade']} {item_data['desc']}"
        )
        return {
            "success": True, "log": log_lines,
            "updated_inv": inv, "item_id": item_id, "item_data": item_data,
        }
    else:
        pct = int(final_rate * 100)
        log_lines.append(f"炉火骤然熄灭，材料化为灰烬……锻造失败（{pct}%成功率）。")
        return {
            "success": False, "log": log_lines,
            "updated_inv": inv, "item_id": None, "item_data": None,
        }


# ═══════════════ 锻造配方列表 ═══════════════

_SLOT_NAMES = {"weapon": "武器", "armor": "护甲", "accessory": "饰品"}


def get_forge_recipes_list(char: dict, inv: dict,
                           forge_recipes: dict = None,
                           forge_realm_bonus: float = None,
                           items: dict = None) -> list:
    """
    返回锻造配方列表，每项包含 id / name / slot / tier / success_rate / req_realm
    / can_craft / ingredients 等字段，供前端展示。
    """
    forge_recipes = forge_recipes or FORGE_RECIPES
    forge_realm_bonus = forge_realm_bonus if forge_realm_bonus is not None else FORGE_REALM_BONUS_PER_LV
    items = items or ITEMS

    result = []
    for rid, r in forge_recipes.items():
        can_craft = char["level"] >= r["req_realm"]
        for mat, count in r["ingredients"].items():
            if inv.get(mat, 0) < count:
                can_craft = False

        base_rate = r["success_rate"]
        realm_bonus = max(0, char["level"] - r["req_realm"]) * forge_realm_bonus
        final_rate = min(0.99, base_rate + realm_bonus)

        slot_name = _SLOT_NAMES.get(r["slot"], r["slot"])
        result.append({
            "id": rid,
            "name": r["name"],
            "slot": r["slot"],
            "slot_name": slot_name,
            "tier": r["tier"],
            "success_rate": int(final_rate * 100),
            "req_realm": realm_name(r["req_realm"]),
            "can_craft": can_craft,
            "ingredients": [
                {"name": items[m]["name"], "need": c, "have": inv.get(m, 0)}
                for m, c in r["ingredients"].items()
            ],
        })
    return result
