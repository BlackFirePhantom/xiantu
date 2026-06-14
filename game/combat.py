"""仙途游戏 - 战斗系统"""

import random
import json
from game_data import (
    LOCATIONS, MONSTERS, ITEMS, DROP_TABLE, PET_EGG_MONSTER_DROPS, MAP_MONSTER_DROPS,
    LOCATION_UNIQUE_DROPS, SURPRISE_EVENTS, ELEMENT_COUNTER, SPIRIT_ROOTS, TECHNIQUES,
    TECHNIQUE_MAX_PROFICIENCY, TECHNIQUE_PROFICIENCY_TIERS, TECHNIQUE_MEDITATE_PROFICIENCY,
    realm_name, spawn_monster,
)
from game.utils import get_full_stats, get_exp_needed


# ═══════════════ 战斗文案 ═══════════════

ATTACK_VERBS = [
    "催动灵力，一掌拍向{m}", "祭出飞剑，剑光一闪斩向{m}",
    "凝聚灵力于拳，轰向{m}", "掐动法诀，一道灵光射向{m}",
    "运转功法，灵力化作刀芒劈向{m}",
]
MONSTER_ATTACK_VERBS = [
    "{m}怒吼一声，一爪拍来", "{m}张口喷出一道妖气",
    "{m}浑身妖力暴涨，猛扑过来", "{m}凝聚妖力，化作暗影袭来",
]


def fmt_attack(n):
    return random.choice(ATTACK_VERBS).format(m=n)


def fmt_monster_attack(n):
    return random.choice(MONSTER_ATTACK_VERBS).format(m=n)


# ═══════════════ 熟练度（战斗专用） ═══════════════

def _get_proficiency(char):
    return json.loads(char["proficiency"]) if char["proficiency"] else {}


def _set_proficiency(uid, prof):
    from models import update_character
    update_character(uid, proficiency=json.dumps(prof))


def _gain_proficiency(char, uid, source="fight"):
    """给所有已学功法增加熟练度，返回 {tech_id: gained} 字典"""
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    if not learned:
        return {}
    prof = _get_proficiency(char)
    gained = {}
    for tid in learned:
        if tid not in TECHNIQUES:
            continue
        cur = prof.get(tid, 0)
        if cur >= TECHNIQUE_MAX_PROFICIENCY:
            continue
        tier = TECHNIQUES[tid].get("tier", "黄阶")
        if source == "fight":
            amount = TECHNIQUE_PROFICIENCY_TIERS.get(tier, 5)
        else:  # meditate
            amount = TECHNIQUE_MEDITATE_PROFICIENCY
        new_val = min(TECHNIQUE_MAX_PROFICIENCY, cur + amount)
        prof[tid] = new_val
        gained[tid] = amount
    if gained:
        _set_proficiency(uid, prof)
    return gained


# ═══════════════ 主战斗函数 ═══════════════

def process_combat(char, session_uid, loc, inv):
    """
    执行一次完整的战斗流程，纯业务逻辑，不依赖 Flask/SocketIO。

    参数:
        char:        角色字典 (get_character 返回值)
        session_uid: 用户 ID (str)
        loc:         当地点字典 (LOCATIONS[...])
        inv:         当前背包字典 {item_id: count}

    返回:
        {
            "log":             [str],        # 战斗日志行
            "won":             bool,         # 是否胜利
            "hp":              int,          # 剩余玩家 HP
            "gold_gain":       int,          # 胜利获得灵石 (0 if lost)
            "kills_increment": int,          # 击杀数增量 (0 or 1)
            "deaths_increment":int,          # 死亡数增量 (0 or 1)
            "gold_lost":       int,          # 死亡损失灵石 (0 if won)
            "exp_lost":        int,          # 死亡损失修为 (0 if won)
            "drops":           [str],        # 掉落物品 ID 列表
            "prof_gained":     {tid: int},   # 熟练度增长 {tech_id: amount}
            "update_location": str or None,  # 死亡时设为 "qingyun_town"
        }
    """
    from models import get_character_inventory, set_character_inventory

    pool = loc.get("monster_pool", [])
    if not pool:
        return {
            "log": ["此处灵气平稳，未察觉妖兽气息。"],
            "won": False, "hp": char["hp"],
            "gold_gain": 0, "kills_increment": 0, "deaths_increment": 0,
            "gold_lost": 0, "exp_lost": 0,
            "drops": [], "prof_gained": {},
            "update_location": None,
        }

    monster_id = random.choice(pool)
    player_lv = char["level"] + loc.get("level_mod", 0)
    monster = spawn_monster(monster_id, player_level=player_lv)

    stats = get_full_stats(char)
    player_hp = char["hp"]
    player_atk = stats["atk"]
    player_def = stats["def"]
    max_hp = stats["max_hp"]

    # ── 五行相克 ──
    sr_element = None
    if char["spirit_root"] and char["spirit_root"] in SPIRIT_ROOTS:
        sr_element = SPIRIT_ROOTS[char["spirit_root"]].get("element")
    element_msg = ""
    if sr_element and monster["element"]:
        if ELEMENT_COUNTER.get(sr_element) == monster["element"]:
            player_atk = int(player_atk * 1.3)
            element_msg = f"（{sr_element}克{monster['element']}，攻击+30%）"
        elif ELEMENT_COUNTER.get(monster["element"]) == sr_element:
            player_atk = int(player_atk * 0.8)
            element_msg = f"（{monster['element']}克{sr_element}，攻击-20%）"

    monster_hp = monster["hp"]
    log = [f"—— 妖兽出没！{monster['name']}（{realm_name(monster['level'])}）{element_msg}——"]

    # ── 战斗类突发事件判定 ──
    bonus_drop_event = None
    for evt in SURPRISE_EVENTS:
        if evt["trigger"] == "fight" and random.random() < evt["chance"]:
            log.append(f"【突发】{evt['text']}")
            eff = evt["effect"]
            if eff == "monster_buff":
                monster[evt["stat"]] = int(monster[evt["stat"]] * evt["mult"])
            elif eff == "monster_debuff":
                monster[evt["stat"]] = max(1, int(monster[evt["stat"]] * evt["mult"]))
            elif eff == "player_buff":
                if evt["stat"] == "atk":
                    player_atk = int(player_atk * evt["mult"])
                elif evt["stat"] == "def":
                    player_def = int(player_def * evt["mult"])
            elif eff == "thunder_strike":
                dmg = random.randint(*evt["dmg_range"])
                monster_hp -= dmg
                log.append(f"天雷造成 {dmg} 点伤害！")
                if monster_hp <= 0:
                    log.append(f"{monster['name']}被天雷劈得灰飞烟灭！")
            elif eff == "extra_monsters":
                extra = random.choice(pool)
                extra_m = spawn_monster(extra, player_level=player_lv)
                monster_hp += extra_m["hp"]
                monster["atk"] = max(monster["atk"], extra_m["atk"])
                log.append(f"增援：{extra_m['name']}（{realm_name(extra_m['level'])}）加入了战斗！")
            elif eff == "bonus_drop":
                bonus_drop_event = evt  # handled after combat
            break  # 只触发一个战斗突发事件

    # ── 回合制战斗循环 ──
    round_num = 0
    while player_hp > 0 and monster_hp > 0:
        round_num += 1
        p_dmg = max(1, player_atk - monster["def"] + random.randint(-2, 3))
        monster_hp -= p_dmg
        log.append(f"[第{round_num}回合] {fmt_attack(monster['name'])}，造成 {p_dmg} 点伤害。")
        if monster_hp <= 0:
            log.append(f"{monster['name']}哀鸣一声，庞大的身躯轰然倒地，妖丹碎裂，灵气四散！")
            break
        m_dmg = max(1, monster["atk"] - player_def + random.randint(-2, 3))
        player_hp -= m_dmg
        log.append(f"[第{round_num}回合] {fmt_monster_attack(monster['name'])}，你受到 {m_dmg} 点伤害。")

    won = player_hp > 0

    # ── 初始化返回值 ──
    result = {
        "log": log, "won": won, "hp": player_hp,
        "gold_gain": 0, "kills_increment": 0, "deaths_increment": 0,
        "gold_lost": 0, "exp_lost": 0,
        "drops": [], "prof_gained": {},
        "update_location": None,
    }

    if won:
        # ── 灵石收益 ──
        gold_gain = monster["gold"] + random.randint(0, monster["gold"] // 2)
        result["gold_gain"] = gold_gain
        result["kills_increment"] = 1

        # ── 熟练度增长 ──
        prof_gained = _gain_proficiency(char, session_uid, source="fight")
        result["prof_gained"] = prof_gained
        prof_parts = []
        for tid, amt in prof_gained.items():
            prof_parts.append(f"{TECHNIQUES[tid]['name']}+{amt}")
        prof_msg = f"（{', '.join(prof_parts)}）" if prof_parts else ""
        log.append(f"斗法胜利！获得 {gold_gain} 灵石。{prof_msg}")

        # ── 掉落计算 ──
        drops = []
        if monster_id in DROP_TABLE:
            for item_id, chance in DROP_TABLE[monster_id]:
                if random.random() < chance:
                    drops.append(item_id)
        # 灵宠蛋掉落
        if monster_id in PET_EGG_MONSTER_DROPS:
            for item_id, chance in PET_EGG_MONSTER_DROPS[monster_id]:
                if random.random() < chance:
                    drops.append(item_id)
        # 藏宝图掉落
        if monster_id in MAP_MONSTER_DROPS:
            for item_id, chance in MAP_MONSTER_DROPS[monster_id]:
                if random.random() < chance:
                    drops.append(item_id)
        # 地点独有掉落
        loc_id = char["location"]
        if loc_id in LOCATION_UNIQUE_DROPS:
            for item_id, chance in LOCATION_UNIQUE_DROPS[loc_id]:
                if random.random() < chance:
                    drops.append(item_id)
        # 战斗突发事件掉落加成
        if bonus_drop_event is not None:
            for drop_item in bonus_drop_event.get("item_pool", []):
                if random.random() < bonus_drop_event.get("drop_chance", 0.5):
                    drops.append(drop_item)

        for item_id in drops:
            inv[item_id] = inv.get(item_id, 0) + 1
            log.append(f"天降机缘，获得【{ITEMS[item_id]['name']}】！")

        result["drops"] = drops

    else:
        # ── 死亡惩罚 ──
        gold_lost = char["gold"] // 5
        needed = get_exp_needed(char["level"])
        if needed != "-" and needed > 0:
            exp_lost = min(needed // 10, char["exp"])
        else:
            exp_lost = 0
        result["gold_lost"] = gold_lost
        result["exp_lost"] = exp_lost
        result["deaths_increment"] = 1
        result["update_location"] = "qingyun_town"

        # 随机掉落背包物品（15%概率，不掉落已装备物品）
        droppable = [
            iid for iid in inv
            if inv[iid] > 0 and iid not in (char["weapon"], char["armor"], char["accessory"])
        ]
        item_lost_msg = ""
        if droppable and random.random() < 0.15:
            lost_id = random.choice(droppable)
            inv[lost_id] -= 1
            if inv[lost_id] <= 0:
                del inv[lost_id]
            item_lost_msg = f"，遗落了【{ITEMS.get(lost_id, {}).get('name', lost_id)}】"

        death_msgs = [
            "你体内灵力耗尽，不敌妖兽……陨落于此。",
            "妖兽一爪拍下，你口吐鲜血，灵力溃散，倒在血泊之中。",
            "你拼死一搏，终究不敌，意识逐渐模糊……",
            "眼前一黑，元神被妖兽震散，肉身轰然倒地。",
        ]
        log.append(random.choice(death_msgs))
        penalty_parts = [f"损失 {gold_lost} 灵石"]
        if exp_lost > 0:
            penalty_parts.append(f"修为 -{exp_lost}")
        if item_lost_msg:
            penalty_parts.append(item_lost_msg.strip("，"))
        log.append("、".join(penalty_parts) + "，元神被传送回青云镇疗伤。")

    return result
