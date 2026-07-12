"""战斗相关的 Socket 事件处理器。"""

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
    LOCATIONS, SPIRIT_ROOTS, TECHNIQUES, ELEMENT_COUNTER, SURPRISE_EVENTS,
    DROP_TABLE, PET_EGG_MONSTER_DROPS, MAP_MONSTER_DROPS, LOCATION_UNIQUE_DROPS,
    ITEMS, realm_name, spawn_monster
)
from game.combat import fmt_attack, fmt_monster_attack
from game.utils import get_full_stats, gain_proficiency, get_exp_needed

# 导入其它 Handler 提供的功能（单向依赖）
from handlers.npc import _check_quest_progress

def do_fight():
    """执行战斗逻辑，可供其它 Handler (如 gameplay) 调用"""
    if "user_id" not in session: return
    game_state.touch_activity(session.get("username", ""))
    char = get_character(session["user_id"])
    if not char: return

    loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
    if loc["safe"]:
        emit("game_msg", {"text": "青云镇内不可动用灵力，此乃镇规。", "type": "info"})
        return
    pool = loc.get("monster_pool", [])
    if not pool:
        emit("game_msg", {"text": "此处灵气平稳，未察觉妖兽气息。", "type": "info"})
        return

    monster_id = random.choice(pool)
    player_lv = char["level"] + loc.get("level_mod", 0)
    monster = spawn_monster(monster_id, player_level=player_lv)

    stats = get_full_stats(char)
    player_hp = char["hp"]
    player_atk = stats["atk"]
    player_def = stats["def"]
    max_hp = stats["max_hp"]

    # 五行相克
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

    # 战斗类突发事件判定
    for evt in SURPRISE_EVENTS:
        if evt["trigger"] == "fight" and random.random() < evt["chance"]:
            log.append(f"【突发】{evt['text']}")
            eff = evt["effect"]
            if eff == "monster_buff":
                monster[evt["stat"]] = int(monster[evt["stat"]] * evt["mult"])
            elif eff == "monster_debuff":
                monster[evt["stat"]] = max(1, int(monster[evt["stat"]] * evt["mult"]))
            elif eff == "player_buff":
                if evt["stat"] == "atk": player_atk = int(player_atk * evt["mult"])
                elif evt["stat"] == "def": player_def = int(player_def * evt["mult"])
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
                pass  # handled after combat
            break  # 只触发一个战斗突发事件

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
    if won:
        gold_gain = monster["gold"] + random.randint(0, monster["gold"] // 2)

        # 熟练度增长
        prof_gained = gain_proficiency(char, session["user_id"], source="fight")
        prof_parts = []
        for tid, amt in prof_gained.items():
            prof_parts.append(f"{TECHNIQUES[tid]['name']}+{amt}")

        prof_msg = f"（{', '.join(prof_parts)}）" if prof_parts else ""
        log.append(f"斗法胜利！获得 {gold_gain} 灵石。{prof_msg}")

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
        for evt in SURPRISE_EVENTS:
            if evt["trigger"] == "fight" and evt.get("effect") == "bonus_drop":
                for drop_item in evt.get("item_pool", []):
                    if random.random() < evt.get("drop_chance", 0.5):
                        drops.append(drop_item)

        inv = get_character_inventory(session["user_id"])
        for item_id in drops:
            inv[item_id] = inv.get(item_id, 0) + 1
            log.append(f"天降机缘，获得【{ITEMS[item_id]['name']}】！")
        set_character_inventory(session["user_id"], inv)

        update_character(session["user_id"], hp=player_hp, gold=char["gold"] + gold_gain, kills=char["kills"] + 1)

        # 任务进度（击杀类）
        char = get_character(session["user_id"])
        _check_quest_progress(char, "kill", monster_id)
    else:
        gold_lost = char["gold"] // 5
        # 修为惩罚：损失当前升级所需修为的10%，不低于0
        needed = get_exp_needed(char["level"])
        if needed != "-" and needed > 0:
            exp_lost = min(needed // 10, char["exp"])
        else:
            exp_lost = 0
        # 随机掉落背包物品（15%概率，不掉落装备）
        item_lost_msg = ""
        inv = get_character_inventory(session["user_id"])
        droppable = [iid for iid in inv if inv[iid] > 0 and iid not in (char["weapon"], char["armor"], char["accessory"])]
        if droppable and random.random() < 0.15:
            lost_id = random.choice(droppable)
            inv[lost_id] -= 1
            if inv[lost_id] <= 0:
                del inv[lost_id]
            set_character_inventory(session["user_id"], inv)
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
        update_character(session["user_id"],
            hp=max_hp // 2,
            gold=max(0, char["gold"] - gold_lost),
            exp=max(0, char["exp"] - exp_lost),
            deaths=char["deaths"] + 1,
            location="qingyun_town")

    emit("fight_log", {"log": log, "won": won})

def register_combat_handlers(socketio):
    @socketio.on("fight")
    def handle_fight():
        do_fight()
