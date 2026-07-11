"""寻宝、升级藏宝图与功法残卷合成相关的 Socket 事件处理器。"""

import json
import random
from flask import session
from flask_socketio import emit

import game_state
from models import get_character, update_character, get_character_inventory, set_character_inventory
from game_data import (
    TREASURE_TABLES, FRAGMENT_RECIPES, TECHNIQUES, ITEMS,
    spawn_monster, realm_name, lookup_item
)
from game.combat import fmt_attack, fmt_monster_attack
from game.utils import get_full_stats

# 导入其它 Handler 提供的功能
from handlers.base import do_get_state

def do_use_map(data):
    """使用藏宝图，供 items.py 的 use_item 触发"""
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    item_id = data.get("item")
    if not item_id: return
    item = lookup_item(item_id)
    if not item or item.get("type") != "treasure_map":
        return

    inv = get_character_inventory(session["user_id"])
    if inv.get(item_id, 0) <= 0:
        emit("game_msg", {"text": "你没有这张藏宝图。", "type": "error"})
        return

    inv[item_id] -= 1
    if inv[item_id] <= 0: del inv[item_id]

    tier = item["map_tier"]
    table = TREASURE_TABLES[tier]
    tier_names = {1: "残破", 2: "完整", 3: "上古"}
    log_lines = [f"你展开{tier_names[tier]}藏宝图，循着标记的方向前行……"]

    # 战斗判定
    fought = False
    if random.random() < table["combat_chance"]:
        monster_id = random.choice(table["combat_monsters"])
        monster = spawn_monster(monster_id, player_level=char["level"])
        log_lines.append(f"突然！一只{monster['name']}（{realm_name(monster['level'])}）从暗处扑出，守护宝藏！")
        
        stats = get_full_stats(char)
        player_hp = char["hp"]
        monster_hp = monster["hp"]
        rnd = 0
        while player_hp > 0 and monster_hp > 0:
            rnd += 1
            p_dmg = max(1, stats["atk"] - monster["def"] + random.randint(-2, 3))
            monster_hp -= p_dmg
            log_lines.append(f"[第{rnd}回合] {fmt_attack(monster['name'])}，造成 {p_dmg} 点伤害。")
            if monster_hp <= 0:
                log_lines.append(f"{monster['name']}倒下了！你继续向宝藏前进。")
                break
            m_dmg = max(1, monster["atk"] - stats["def"] + random.randint(-2, 3))
            player_hp -= m_dmg
            log_lines.append(f"[第{rnd}回合] {fmt_monster_attack(monster['name'])}，受到 {m_dmg} 点伤害。")
        fought = True
        if player_hp <= 0:
            log_lines.append("你不敌守宝妖兽，藏宝图在战斗中损毁……")
            update_character(session["user_id"], hp=max(1, stats["max_hp"] // 3),
                             gold=max(0, char["gold"] - 20), deaths=char["deaths"] + 1)
            set_character_inventory(session["user_id"], inv)
            emit("fight_log", {"log": log_lines, "won": False})
            return
        
        update_character(session["user_id"], hp=player_hp)
        char = get_character(session["user_id"])

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

    set_character_inventory(session["user_id"], inv)
    update_character(session["user_id"], exp=char["exp"] + exp_gain, gold=char["gold"] + gold_gain)

    emit("fight_log", {"log": log_lines, "won": True})
    do_get_state(session["user_id"])

def do_combine_fragments(data):
    """合成功法残卷，供 items.py 的 use_item 触发"""
    if "user_id" not in session: return
    char = get_character(session["user_id"])
    if not char: return
    group = data.get("group")
    if not group or group not in FRAGMENT_RECIPES:
        return

    technique_id, fragments = FRAGMENT_RECIPES[group]
    if technique_id in TECHNIQUES:
        t = TECHNIQUES[technique_id]
        learned = json.loads(char["techniques"]) if char["techniques"] else []
        if technique_id in learned:
            emit("game_msg", {"text": f"你已经领悟了【{t['name']}】。", "type": "error"})
            return
        if char["level"] < t["req_realm"]:
            emit("game_msg", {"text": f"境界不足，需要{realm_name(t['req_realm'])}才能领悟。", "type": "error"})
            return

    inv = get_character_inventory(session["user_id"])
    for frag_id in fragments:
        if inv.get(frag_id, 0) <= 0:
            frag_name = ITEMS.get(frag_id, {}).get("name", frag_id)
            emit("game_msg", {"text": f"缺少【{frag_name}】，无法合成。", "type": "error"})
            return

    # 扣除残卷
    for frag_id in fragments:
        inv[frag_id] -= 1
        if inv[frag_id] <= 0: del inv[frag_id]
    set_character_inventory(session["user_id"], inv)

    # 学习功法
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    if technique_id not in learned:
        learned.append(technique_id)
        update_character(session["user_id"], techniques=json.dumps(learned))

    t = TECHNIQUES.get(technique_id, {})
    names = "、".join([ITEMS.get(f,{}).get("name","?") for f in fragments])
    emit("game_msg", {"text": f"你将{names}拼合在一起，残卷上的文字忽然流转起来——领悟了完整功法【{t.get('name', technique_id)}】（{t.get('tier', '')}）！", "type": "buff"})
    do_get_state(session["user_id"])

def register_adventure_handlers(socketio):
    @socketio.on("use_map")
    def handle_use_map(data):
        do_use_map(data)

    @socketio.on("upgrade_map")
    def handle_upgrade_map(data):
        if "user_id" not in session: return
        char = get_character(session["user_id"])
        if not char: return
        item_id = data.get("item")
        if not item_id: return
        item = lookup_item(item_id)
        if not item or item.get("type") != "treasure_map":
            emit("game_msg", {"text": "只能对藏宝图使用。", "type": "error"})
            return
        if item["map_tier"] >= 3:
            emit("game_msg", {"text": "已经是最高品质的藏宝图了。", "type": "error"})
            return

        # 等级限制
        upgrade_req = {1: 5, 2: 10}
        req_lv = upgrade_req.get(item["map_tier"], 99)
        if char["level"] < req_lv:
            emit("game_msg", {"text": f"境界不足！升级需要{realm_name(req_lv)}（当前{realm_name(char['level'])}）。", "type": "error"})
            return

        # 材料限制
        upgrade_mats = {
            1: {"yaogu": 3, "hantie_kuang": 2},
            2: {"yaodan": 2, "xuanjin_shi": 3, "tianwai_yuntie": 1},
        }
        need_mats = upgrade_mats.get(item["map_tier"], {})

        inv = get_character_inventory(session["user_id"])
        if inv.get("map_compass", 0) <= 0:
            emit("game_msg", {"text": "你没有寻宝罗盘。", "type": "error"})
            return
        if inv.get(item_id, 0) <= 0:
            emit("game_msg", {"text": "你没有这张藏宝图。", "type": "error"})
            return

        # 检查材料
        missing = []
        for mat_id, need in need_mats.items():
            have = inv.get(mat_id, 0)
            if have < need:
                mat_name = ITEMS.get(mat_id, {}).get("name", mat_id)
                missing.append(f"{mat_name}({have}/{need})")
        if missing:
            emit("game_msg", {"text": f"材料不足：{'、'.join(missing)}", "type": "error"})
            return

        # 扣除材料 + 罗盘 + 旧图
        new_tier = item["map_tier"] + 1
        new_map_id = {2: "map_rare", 3: "map_legend"}[new_tier]
        for mat_id, need in need_mats.items():
            inv[mat_id] -= need
            if inv[mat_id] <= 0: del inv[mat_id]
        inv[item_id] -= 1
        if inv[item_id] <= 0: del inv[item_id]
        inv["map_compass"] -= 1
        if inv["map_compass"] <= 0: del inv["map_compass"]
        inv[new_map_id] = inv.get(new_map_id, 0) + 1
        set_character_inventory(session["user_id"], inv)

        tier_names = {2: "完整藏宝图", 3: "上古藏宝图"}
        emit("game_msg", {"text": f"寻宝罗盘灵光闪烁，藏宝图品质提升！获得【{tier_names[new_tier]}】！", "type": "buff"})
        do_get_state(session["user_id"])

    @socketio.on("combine_fragments")
    def handle_combine_fragments(data):
        do_combine_fragments(data)
