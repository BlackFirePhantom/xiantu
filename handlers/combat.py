"""战斗相关的 Socket 事件处理器（回合制）。"""

import random
import time
import logging
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
    ITEMS, MONSTERS, realm_name, spawn_monster
)
from game.combat import fmt_attack, fmt_monster_attack
from game.combat_engine import (
    calc_damage as _calc_damage,
    create_combat_state,
    decrement_buffs as _decrement_buffs,
    effective_atk as _effective_atk,
    effective_def as _effective_def,
    execute_skill as _execute_skill,
    get_player_skills as _get_player_skills,
    process_player_action as _process_player_action,
    serialize_combat_state,
)
from game.utils import get_full_stats, gain_proficiency, get_exp_needed, calc_max_mp
from handlers.npc import _check_quest_progress

logger = logging.getLogger("xiantu.handlers.combat")


def do_fight():
    """开始一场回合制战斗"""
    if "user_id" not in session:
        return
    game_state.touch_activity(session.get("username", ""))
    user_id = session["user_id"]
    char = get_character(user_id)
    if not char:
        return

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
    sr_element = None
    if char["spirit_root"] and char["spirit_root"] in SPIRIT_ROOTS:
        sr_element = SPIRIT_ROOTS[char["spirit_root"]].get("element")
    element_msg = ""
    player_atk = stats["atk"]
    if sr_element and monster["element"]:
        if ELEMENT_COUNTER.get(sr_element) == monster["element"]:
            player_atk = int(player_atk * 1.3)
            element_msg = f"（{sr_element}克{monster['element']}，攻击+30%）"
        elif ELEMENT_COUNTER.get(monster["element"]) == sr_element:
            player_atk = int(player_atk * 0.8)
            element_msg = f"（{monster['element']}克{sr_element}，攻击-20%）"

    log = [f"-- 妖兽出没！{monster['name']}（{realm_name(monster['level'])}）{element_msg}--"]

    # 战斗类突发事件
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
                    pass
            elif eff == "thunder_strike":
                dmg = random.randint(*evt["dmg_range"])
                monster["hp"] -= dmg
                log.append(f"天雷造成 {dmg} 点伤害！")
                if monster["hp"] <= 0:
                    log.append(f"{monster['name']}被天雷劈得灰飞烟灭！")
            elif eff == "extra_monsters":
                extra = random.choice(pool)
                extra_m = spawn_monster(extra, player_level=player_lv)
                monster["hp"] += extra_m["hp"]
                monster["atk"] = max(monster["atk"], extra_m["atk"])
                log.append(f"增援：{extra_m['name']}（{realm_name(extra_m['level'])}）加入了战斗！")
            elif eff == "bonus_drop":
                bonus_drop_event = evt
            break

    max_mp = stats.get("max_mp", calc_max_mp(char["level"]))
    combat = create_combat_state(
        kind="wild",
        monster=monster,
        monster_hp=monster["hp"],
        monster_max_hp=monster["hp"],
        monster_atk=monster["atk"],
        monster_def=monster["def"],
        player_hp=char["hp"],
        player_max_hp=stats["max_hp"],
        player_mp=char.get("mp", max_mp) if isinstance(char.get("mp"), int) else max_mp,
        player_max_mp=max_mp,
        player_atk=player_atk,
        player_def=stats["def"],
        log=log,
        monster_id=monster_id,
        loc_id=char["location"],
        bonus_drop_event=bonus_drop_event,
        element_msg=element_msg,
        monster_element=monster.get("element"),
        player_element=sr_element,
        char_level=char["level"],
        last_action_at=time.time(),
        username=session.get("username", ""),
    )

    with game_state.combat_lock:
        game_state.active_combats[user_id] = combat

    skills = _get_player_skills(char)
    monster_view = {
        "name": monster["name"],
        "level": monster["level"],
        "element": monster.get("element"),
        "skills": monster.get("skills", []),
        "atk": monster["atk"],
        "def": monster["def"],
        "realm": realm_name(monster["level"]),
    }
    emit("combat_start", serialize_combat_state(
        combat,
        monster=monster_view,
        skills=skills,
    ))


def _monster_turn(combat):
    """怪物AI回合，返回日志列表"""
    log = []
    combat["monster_defending"] = False
    monster = combat["monster"]

    # 检查怪物技能
    skills = monster.get("skills", [])
    used_skill = None
    for skill in skills:
        if random.random() < skill.get("chance", 0.2):
            used_skill = skill
            break

    if used_skill:
        log = _execute_skill(combat, used_skill, None, log, is_player=False)
    else:
        roll = random.random()
        if roll < 0.10:
            combat["monster_defending"] = True
            log.append(f"[第{combat['round']}回合] {monster['name']}蓄力防御，减伤50%。")
        elif roll < 0.30:
            dmg = max(1, int(_effective_atk(combat, is_player=False) * 1.3) - _effective_def(combat, is_player=True) + random.randint(-2, 3))
            if combat["defending"]:
                dmg = dmg // 2
            combat["player_hp"] -= dmg
            log.append(f"[第{combat['round']}回合] {monster['name']}猛然暴起，重击造成 {dmg} 点伤害！")
        else:
            dmg = _calc_damage(combat, is_player_attacker=False)
            if combat["defending"]:
                dmg = dmg // 2
            combat["player_hp"] -= dmg
            log.append(f"[第{combat['round']}回合] {fmt_monster_attack(monster['name'])}，你受到 {dmg} 点伤害。")

    return log


def _finish_combat(user_id, combat, char):
    """战斗结束结算"""
    won = combat.get("_fled", False) is False and combat["player_hp"] > 0
    fled = combat.get("_fled", False)
    monster_id = combat["monster_id"]
    log = combat["log"]

    if fled:
        update_character(user_id, hp=combat["player_hp"])
        return {"won": False, "fled": True, "log": log}

    if won:
        monster = combat["monster"]
        gold_gain = monster["gold"] + random.randint(0, monster["gold"] // 2)
        prof_gained = gain_proficiency(char, user_id, source="fight")
        prof_parts = [f"{TECHNIQUES[tid]['name']}+{amt}" for tid, amt in prof_gained.items() if tid in TECHNIQUES]
        prof_msg = f"（{', '.join(prof_parts)}）" if prof_parts else ""
        log.append(f"斗法胜利！获得 {gold_gain} 灵石。{prof_msg}")

        drops = []
        if monster_id in DROP_TABLE:
            for item_id, chance in DROP_TABLE[monster_id]:
                if random.random() < chance:
                    drops.append(item_id)
        if monster_id in PET_EGG_MONSTER_DROPS:
            for item_id, chance in PET_EGG_MONSTER_DROPS[monster_id]:
                if random.random() < chance:
                    drops.append(item_id)
        if monster_id in MAP_MONSTER_DROPS:
            for item_id, chance in MAP_MONSTER_DROPS[monster_id]:
                if random.random() < chance:
                    drops.append(item_id)
        loc_id = combat["loc_id"]
        if loc_id in LOCATION_UNIQUE_DROPS:
            for item_id, chance in LOCATION_UNIQUE_DROPS[loc_id]:
                if random.random() < chance:
                    drops.append(item_id)
        if combat.get("bonus_drop_event"):
            for drop_item in combat["bonus_drop_event"].get("item_pool", []):
                if random.random() < combat["bonus_drop_event"].get("drop_chance", 0.5):
                    drops.append(drop_item)

        inv = get_character_inventory(user_id)
        for item_id in drops:
            inv[item_id] = inv.get(item_id, 0) + 1
            log.append(f"天降机缘，获得【{ITEMS[item_id]['name']}】！")
        set_character_inventory(user_id, inv)

        max_mp = combat["player_max_mp"]
        update_character(user_id, hp=combat["player_hp"], mp=combat["player_mp"],
                         gold=char["gold"] + gold_gain, kills=char["kills"] + 1)
        char = get_character(user_id)
        _check_quest_progress(char, "kill", monster_id)
        return {"won": True, "log": log, "gold_gain": gold_gain, "drops": drops}
    else:
        gold_lost = char["gold"] // 5
        needed = get_exp_needed(char["level"])
        if needed != "-" and needed > 0:
            exp_lost = min(needed // 10, char["exp"])
        else:
            exp_lost = 0
        inv = get_character_inventory(user_id)
        droppable = [iid for iid in inv if inv[iid] > 0 and iid not in (char["weapon"], char["armor"], char["accessory"])]
        item_lost_msg = ""
        if droppable and random.random() < 0.15:
            lost_id = random.choice(droppable)
            inv[lost_id] -= 1
            if inv[lost_id] <= 0:
                del inv[lost_id]
            set_character_inventory(user_id, inv)
            item_lost_msg = f"，遗落了【{ITEMS.get(lost_id, {}).get('name', lost_id)}】"

        death_msgs = ["你体内灵力耗尽，不敌妖兽……陨落于此。",
                       "妖兽一爪拍下，你口吐鲜血，灵力溃散，倒在血泊之中。",
                       "你拼死一搏，终究不敌，意识逐渐模糊……",
                       "眼前一黑，元神被妖兽震散，肉身轰然倒地。"]
        log.append(random.choice(death_msgs))
        penalty_parts = [f"损失 {gold_lost} 灵石"]
        if exp_lost > 0:
            penalty_parts.append(f"修为 -{exp_lost}")
        if item_lost_msg:
            penalty_parts.append(item_lost_msg.strip("，"))
        log.append("、".join(penalty_parts) + "，元神被传送回青云镇疗伤。")

        update_character(user_id, hp=combat["player_max_hp"] // 2,
                         mp=combat["player_max_mp"],
                         gold=max(0, char["gold"] - gold_lost),
                         exp=max(0, char["exp"] - exp_lost),
                         deaths=char["deaths"] + 1, location="qingyun_town")
        return {"won": False, "log": log}


def do_fight_action(data):
    """处理玩家每回合行动"""
    if "user_id" not in session:
        return
    user_id = session["user_id"]
    game_state.touch_activity(session.get("username", ""))

    # 持锁覆盖整个 action 处理流程，防止同用户多连接并发 fight_action
    # 导致 combat dict 的 in-place mutation 竞态。
    with game_state.combat_lock:
        combat = game_state.active_combats.get(user_id)
        if not combat:
            emit("game_msg", {"text": "没有进行中的战斗。", "type": "error"})
            return

        # 更新最后操作时间，防止后台超时扫描误清理
        combat["last_action_at"] = time.time()

        char = get_character(user_id)
        if not char:
            return

        action = data.get("action", "attack")
        skill_id = data.get("skill_id")

        # 处理玩家行动
        player_log = _process_player_action(combat, action, skill_id, char, user_id)
        combat["log"].extend(player_log)

        # 检查怪物是否已死或玩家逃跑
        fled = combat.get("_fled", False)
        if fled:
            result = _finish_combat(user_id, combat, char)
            game_state.active_combats.pop(user_id, None)
            emit("combat_end", {"won": False, "fled": True, "log": result["log"]})
            from handlers.base import do_get_state
            do_get_state(user_id)
            return

        if combat["monster_hp"] <= 0:
            result = _finish_combat(user_id, combat, char)
            game_state.active_combats.pop(user_id, None)
            emit("combat_end", result)
            from handlers.base import do_get_state
            do_get_state(user_id)
            return

        # 怪物回合
        monster_log = _monster_turn(combat)
        combat["log"].extend(monster_log)

        # 递减buff/debuff
        _decrement_buffs(combat)

        # MP恢复
        combat["player_mp"] = min(combat["player_max_mp"], combat["player_mp"] + 5)

        # 检查玩家是否死亡
        if combat["player_hp"] <= 0:
            combat["player_hp"] = 0
            result = _finish_combat(user_id, combat, char)
            game_state.active_combats.pop(user_id, None)
            emit("combat_end", result)
            from handlers.base import do_get_state
            do_get_state(user_id)
            return

        # 进入下一回合
        combat["round"] += 1
        skills = _get_player_skills(char)
        emit("combat_round", {
            "round": combat["round"],
            "log": player_log + monster_log,
            "player_hp": combat["player_hp"], "player_max_hp": combat["player_max_hp"],
            "player_mp": combat["player_mp"], "player_max_mp": combat["player_max_mp"],
            "monster_hp": max(0, combat["monster_hp"]), "monster_max_hp": combat["monster_max_hp"],
            "player_buffs": combat["player_buffs"], "player_debuffs": combat["player_debuffs"],
            "monster_buffs": combat["monster_buffs"], "monster_debuffs": combat["monster_debuffs"],
            "skills": skills,
        })


def register_combat_handlers(socketio):
    @socketio.on("fight")
    def handle_fight():
        do_fight()

    @socketio.on("fight_action")
    def handle_fight_action(data):
        do_fight_action(data)
