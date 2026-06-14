"""藏宝图系统逻辑"""

import random
import json
from game_data import (
    ITEMS, TREASURE_TABLES, FRAGMENT_RECIPES, TECHNIQUES,
    realm_name, spawn_monster, lookup_item,
)
from game.utils import get_full_stats


ATTACK_VERBS = [
    "催动灵力，一掌拍向{m}", "祭出飞剑，剑光一闪斩向{m}",
    "凝聚灵力于拳，轰向{m}", "掐动法诀，一道灵光射向{m}",
    "运转功法，灵力化作刀芒劈向{m}",
]
MONSTER_ATTACK_VERBS = [
    "{m}怒吼一声，一爪拍来", "{m}张口喷出一道妖气",
    "{m}浑身妖力暴涨，猛扑过来", "{m}凝聚妖力，化作暗影袭来",
]


def use_treasure_map(char, inv, item_id, uid):
    """使用藏宝图寻宝，返回结果 dict"""
    item = lookup_item(item_id)
    if not item or item.get("type") != "treasure_map":
        return {"success": False, "message": "这不是藏宝图。"}

    if inv.get(item_id, 0) <= 0:
        return {"success": False, "message": "你没有这张藏宝图。"}

    inv[item_id] -= 1
    if inv[item_id] <= 0:
        del inv[item_id]

    tier = item["map_tier"]
    table = TREASURE_TABLES[tier]
    tier_names = {1: "残破", 2: "完整", 3: "上古"}
    log_lines = [f"你展开{tier_names[tier]}藏宝图，循着标记的方向前行……"]

    stats = get_full_stats(char)

    # 战斗判定
    if random.random() < table["combat_chance"]:
        monster_id = random.choice(table["combat_monsters"])
        monster = spawn_monster(monster_id, player_level=char["level"])
        log_lines.append(f"突然！一只{monster['name']}（{realm_name(monster['level'])}）从暗处扑出，守护宝藏！")

        player_hp = char["hp"]
        monster_hp = monster["hp"]
        rnd = 0
        while player_hp > 0 and monster_hp > 0:
            rnd += 1
            p_dmg = max(1, stats["atk"] - monster["def"] + random.randint(-2, 3))
            monster_hp -= p_dmg
            log_lines.append(f"[第{rnd}回合] {random.choice(ATTACK_VERBS).format(m=monster['name'])}，造成 {p_dmg} 点伤害。")
            if monster_hp <= 0:
                log_lines.append(f"{monster['name']}倒下了！你继续向宝藏前进。")
                break
            m_dmg = max(1, monster["atk"] - stats["def"] + random.randint(-2, 3))
            player_hp -= m_dmg
            log_lines.append(f"[第{rnd}回合] {random.choice(MONSTER_ATTACK_VERBS).format(m=monster['name'])}，受到 {m_dmg} 点伤害。")

        if player_hp <= 0:
            log_lines.append("你不敌守宝妖兽，藏宝图在战斗中损毁……")
            return {
                "success": True, "log": log_lines, "won": False,
                "hp": max(1, stats["max_hp"] // 3), "gold_change": -20,
                "deaths_increment": 1, "updated_inv": inv,
            }
        char = dict(char)
        char["hp"] = player_hp

    # 获得奖励
    gold_gain = random.randint(*table["gold_range"])
    exp_gain = random.randint(*table["exp_range"])
    log_lines.append(f"你找到了宝藏！获得 {gold_gain} 灵石、{exp_gain} 修为。")

    item_count = random.randint(*table["item_count"])
    rewards = []
    for _ in range(item_count):
        r = random.random()
        cum = 0
        for iid, chance in table["item_pool"]:
            cum += chance
            if r < cum:
                rewards.append(iid)
                break

    # 功法残卷
    if random.random() < table.get("fragment_chance", 0):
        frag_pool = table.get("fragment_pool", [])
        if frag_pool:
            frag = random.choice(frag_pool)
            rewards.append(frag)

    for iid in rewards:
        inv[iid] = inv.get(iid, 0) + 1
        log_lines.append(f"获得【{ITEMS[iid]['name']}】！")

    return {
        "success": True, "log": log_lines, "won": True,
        "hp": char.get("hp", stats["max_hp"]),
        "gold_gain": gold_gain, "exp_gain": exp_gain,
        "updated_inv": inv,
    }


def upgrade_treasure_map(char, inv, item_id):
    """升级藏宝图，返回结果 dict"""
    item = lookup_item(item_id)
    if not item or item.get("type") != "treasure_map":
        return {"success": False, "message": "只能对藏宝图使用。"}
    if item["map_tier"] >= 3:
        return {"success": False, "message": "已经是最高品质的藏宝图了。"}

    upgrade_req = {1: 5, 2: 10}
    req_lv = upgrade_req.get(item["map_tier"], 99)
    if char["level"] < req_lv:
        return {"success": False, "message": f"境界不足！升级需要{realm_name(req_lv)}（当前{realm_name(char['level'])}）。"}

    upgrade_mats = {
        1: {"yaogu": 3, "hantie_kuang": 2},
        2: {"yaodan": 2, "xuanjin_shi": 3, "tianwai_yuntie": 1},
    }
    need_mats = upgrade_mats.get(item["map_tier"], {})

    if inv.get("map_compass", 0) <= 0:
        return {"success": False, "message": "你没有寻宝罗盘。"}
    if inv.get(item_id, 0) <= 0:
        return {"success": False, "message": "你没有这张藏宝图。"}

    missing = []
    for mat_id, need in need_mats.items():
        have = inv.get(mat_id, 0)
        if have < need:
            mat_name = ITEMS.get(mat_id, {}).get("name", mat_id)
            missing.append(f"{mat_name}({have}/{need})")
    if missing:
        return {"success": False, "message": f"材料不足：{'、'.join(missing)}"}

    new_tier = item["map_tier"] + 1
    new_map_id = {2: "map_rare", 3: "map_legend"}[new_tier]
    for mat_id, need in need_mats.items():
        inv[mat_id] -= need
        if inv[mat_id] <= 0:
            del inv[mat_id]
    inv[item_id] -= 1
    if inv[item_id] <= 0:
        del inv[item_id]
    inv["map_compass"] -= 1
    if inv["map_compass"] <= 0:
        del inv["map_compass"]
    inv[new_map_id] = inv.get(new_map_id, 0) + 1

    tier_names = {2: "完整藏宝图", 3: "上古藏宝图"}
    return {
        "success": True,
        "message": f"寻宝罗盘灵光闪烁，藏宝图品质提升！获得【{tier_names[new_tier]}】！",
        "updated_inv": inv,
    }


def combine_fragments(char, inv, group):
    """合成功法残卷，返回结果 dict"""
    if not group or group not in FRAGMENT_RECIPES:
        return {"success": False, "message": "未知的合成配方。"}

    technique_id, fragments = FRAGMENT_RECIPES[group]
    if technique_id in TECHNIQUES:
        t = TECHNIQUES[technique_id]
        learned = json.loads(char["techniques"]) if char["techniques"] else []
        if technique_id in learned:
            return {"success": False, "message": f"你已经领悟了【{t['name']}】。"}
        if char["level"] < t["req_realm"]:
            return {"success": False, "message": f"境界不足，需要{realm_name(t['req_realm'])}才能领悟。"}

    for frag_id in fragments:
        if inv.get(frag_id, 0) <= 0:
            frag_name = ITEMS.get(frag_id, {}).get("name", frag_id)
            return {"success": False, "message": f"缺少【{frag_name}】，无法合成。"}

    for frag_id in fragments:
        inv[frag_id] -= 1
        if inv[frag_id] <= 0:
            del inv[frag_id]

    learned = json.loads(char["techniques"]) if char["techniques"] else []
    if technique_id not in learned:
        learned.append(technique_id)

    t = TECHNIQUES.get(technique_id, {})
    names = "、".join([ITEMS.get(f, {}).get("name", "?") for f in fragments])
    message = f"你将{names}拼合在一起，残卷上的文字忽然流转起来——领悟了完整功法【{t.get('name', technique_id)}】（{t.get('tier', '')}）！"

    return {
        "success": True, "message": message,
        "updated_inv": inv, "updated_techniques": learned,
    }
