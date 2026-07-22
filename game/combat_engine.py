"""Reusable turn-based combat rules shared by normal, PvP, and realm combat."""

import json
import random

from game.combat import fmt_attack
from game_data import TECHNIQUES


COMBAT_SCHEMA_VERSION = 1


def create_combat_state(
    *,
    kind,
    monster,
    monster_hp,
    monster_max_hp,
    monster_atk,
    monster_def,
    player_hp,
    player_max_hp,
    player_mp,
    player_max_mp,
    player_atk,
    player_def,
    round_number=1,
    log=None,
    **metadata,
):
    """Create the canonical mutable state consumed by all turn rules."""
    state = {
        "schema_version": COMBAT_SCHEMA_VERSION,
        "kind": kind,
        "monster": monster,
        "monster_hp": monster_hp,
        "monster_max_hp": monster_max_hp,
        "monster_atk": monster_atk,
        "monster_def": monster_def,
        "player_hp": player_hp,
        "player_max_hp": player_max_hp,
        "player_mp": player_mp,
        "player_max_mp": player_max_mp,
        "player_atk": player_atk,
        "player_def": player_def,
        "round": round_number,
        "log": list(log or []),
        "player_buffs": {},
        "player_debuffs": {},
        "monster_buffs": {},
        "monster_debuffs": {},
        "defending": False,
        "monster_defending": False,
    }
    state.update(metadata)
    return state


def serialize_combat_state(combat, *, monster=None, skills=None):
    """Expose one stable frontend contract for a turn-based encounter."""
    return {
        "schema_version": combat.get("schema_version", COMBAT_SCHEMA_VERSION),
        "kind": combat.get("kind", "wild"),
        "monster": monster or combat["monster"],
        "monster_hp": combat["monster_hp"],
        "monster_max_hp": combat["monster_max_hp"],
        "player_hp": combat["player_hp"],
        "player_max_hp": combat["player_max_hp"],
        "player_mp": combat["player_mp"],
        "player_max_mp": combat["player_max_mp"],
        "skills": list(skills or []),
        "round": combat["round"],
        "log": list(combat.get("log", [])),
        "player_buffs": combat.get("player_buffs", {}),
        "monster_buffs": combat.get("monster_buffs", {}),
    }


def get_player_skills(char):
    """Return the usable skills learned by a character."""
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    skills = []
    for technique_id in learned:
        technique = TECHNIQUES.get(technique_id)
        if technique and technique.get("skill"):
            skills.append({
                "tech_id": technique_id,
                "name": technique["name"],
                "skill": technique["skill"],
            })
    return skills


def effective_atk(combat, is_player):
    """Calculate attack after buffs and debuffs."""
    prefix = "player" if is_player else "monster"
    base = combat[f"{prefix}_atk"]
    mult = combat[f"{prefix}_buffs"].get("atk", {}).get("mult", 1.0)
    debuff_mult = combat[f"{prefix}_debuffs"].get("atk", {}).get("mult", 1.0)
    return int(base * mult * debuff_mult)


def effective_def(combat, is_player):
    """Calculate defense after buffs."""
    prefix = "player" if is_player else "monster"
    base = combat[f"{prefix}_def"]
    mult = combat[f"{prefix}_buffs"].get("def", {}).get("mult", 1.0)
    return int(base * mult)


def decrement_buffs(combat):
    """Decrement all timed effects at the end of a round."""
    for buff_dict in ("player_buffs", "player_debuffs", "monster_buffs", "monster_debuffs"):
        expired = []
        for stat, info in combat[buff_dict].items():
            info["rounds"] -= 1
            if info["rounds"] <= 0:
                expired.append(stat)
        for stat in expired:
            del combat[buff_dict][stat]


def process_player_action(combat, action, skill_id, char, user_id=None):
    """Apply one player action and return its combat log."""
    log = []
    combat["defending"] = False

    if action == "defend":
        combat["defending"] = True
        heal = max(1, combat["player_max_hp"] // 20)
        combat["player_hp"] = min(combat["player_max_hp"], combat["player_hp"] + heal)
        log.append(f"[第{combat['round']}回合] 你屏息凝神，防御姿态，恢复 {heal} 气血。")
        return log

    if action == "flee":
        flee_chance = min(0.8, 0.3 + (combat["char_level"] - combat["monster"]["level"]) * 0.1)
        if random.random() < flee_chance:
            log.append("你御剑遁走，成功脱离战斗！")
            combat["_fled"] = True
        else:
            log.append("你转身欲逃，却被妖兽截住了去路！")
        return log

    if action == "skill" and skill_id:
        technique = TECHNIQUES.get(skill_id)
        if not technique or not technique.get("skill"):
            action = "attack"
        else:
            skill = technique["skill"]
            mp_cost = skill.get("mp_cost", 0)
            if combat["player_mp"] < mp_cost:
                log.append(f"灵力不足，无法施展【{skill['name']}】！改为普通攻击。")
                action = "attack"
            else:
                combat["player_mp"] -= mp_cost
                return execute_skill(combat, skill, char, log, is_player=True)

    if action == "attack":
        damage = calc_damage(combat, is_player_attacker=True)
        combat["monster_hp"] -= damage
        log.append(f"[第{combat['round']}回合] {fmt_attack(combat['monster']['name'])}，造成 {damage} 点伤害。")
        if combat["monster_hp"] <= 0:
            log.append(f"{combat['monster']['name']}哀鸣一声，庞大的身躯轰然倒地，妖丹碎裂，灵气四散！")

    return log


def execute_skill(combat, skill, char, log, is_player):
    """Apply a technique to the mutable combat state."""
    if is_player:
        attacker_name = "你"
        target_name = combat["monster"]["name"]
        attack = effective_atk(combat, is_player=True)
        defense = effective_def(combat, is_player=False)
        max_hp = combat["player_max_hp"]
    else:
        attacker_name = combat["monster"]["name"]
        target_name = "你"
        attack = effective_atk(combat, is_player=False)
        defense = effective_def(combat, is_player=True)
        max_hp = combat["player_max_hp"]

    skill_type = skill["type"]
    skill_name = skill["name"]

    if skill_type == "attack":
        damage = max(1, int(attack * skill["power"]) - defense + random.randint(-2, 3))
        if is_player:
            combat["monster_hp"] -= damage
            log.append(f"[第{combat['round']}回合] 你施展【{skill_name}】，造成 {damage} 点伤害！")
            if combat["monster_hp"] <= 0:
                log.append(f"{combat['monster']['name']}哀鸣一声，庞大的身躯轰然倒地！")
        else:
            if combat["defending"]:
                damage //= 2
            combat["player_hp"] -= damage
            log.append(f"[第{combat['round']}回合] {combat['monster']['name']}施展【{skill_name}】，你受到 {damage} 点伤害！")

    elif skill_type == "multi_hit":
        hits = skill.get("hits", 2)
        total = 0
        for index in range(hits):
            damage = max(1, int(attack * skill["power"]) - defense + random.randint(-2, 3))
            total += damage
            log.append(f"  第{index + 1}击：{damage} 点伤害！")
        if is_player:
            combat["monster_hp"] -= total
            log.insert(-hits, f"[第{combat['round']}回合] 你施展【{skill_name}】，{hits}连击！")
            if combat["monster_hp"] <= 0:
                log.append(f"{combat['monster']['name']}在连击中倒下！")
        else:
            if combat["defending"]:
                total //= 2
            combat["player_hp"] -= total
            log.insert(-hits, f"[第{combat['round']}回合] {combat['monster']['name']}施展【{skill_name}】，{hits}连击！")

    elif skill_type == "heal":
        heal = int(max_hp * skill["power"])
        if is_player:
            combat["player_hp"] = min(max_hp, combat["player_hp"] + heal)
            log.append(f"[第{combat['round']}回合] 你施展【{skill_name}】，恢复 {heal} 气血。")
        else:
            combat["monster_hp"] = min(combat["monster_max_hp"], combat["monster_hp"] + heal)
            log.append(f"[第{combat['round']}回合] {combat['monster']['name']}施展【{skill_name}】，恢复 {heal} 气血。")

    elif skill_type == "defense":
        duration = skill.get("duration", 2)
        power = skill.get("power", 0.3)
        buffs = combat["player_buffs"] if is_player else combat["monster_buffs"]
        buffs["def"] = {"mult": 1.0 - power, "rounds": duration}
        if is_player:
            log.append(f"[第{combat['round']}回合] 你施展【{skill_name}】，减伤{int(power * 100)}%，持续{duration}回合。")
        else:
            log.append(f"[第{combat['round']}回合] {combat['monster']['name']}施展【{skill_name}】，减伤{int(power * 100)}%！")

    elif skill_type == "buff":
        duration = skill.get("duration", 3)
        power = skill.get("power", 0.2)
        target = skill.get("target", "atk")
        buffs = combat["player_buffs"] if is_player else combat["monster_buffs"]
        targets = ("atk", "def") if target == "all" else (target,)
        for stat in targets:
            buffs[stat] = {"mult": 1.0 + power, "rounds": duration}
        if is_player:
            log.append(f"[第{combat['round']}回合] 你施展【{skill_name}】，{target}+{int(power * 100)}%，持续{duration}回合。")
        else:
            log.append(f"[第{combat['round']}回合] {combat['monster']['name']}施展【{skill_name}】，{target}提升！")

    elif skill_type == "debuff":
        duration = skill.get("duration", 2)
        power = skill.get("power", 0.3)
        debuff_target = skill.get("target", "monster_atk")
        stat = "atk" if "atk" in debuff_target else "def"
        debuffs = combat["monster_debuffs"] if is_player else combat["player_debuffs"]
        debuffs[stat] = {"mult": 1.0 - power, "rounds": duration}
        if is_player:
            log.append(f"[第{combat['round']}回合] 你施展【{skill_name}】，{target_name}的{stat}-{int(power * 100)}%！")
        else:
            log.append(f"[第{combat['round']}回合] {attacker_name}施展【{skill_name}】，你的{stat}-{int(power * 100)}%！")

    elif skill_type == "lifesteal":
        damage = max(1, int(attack * skill["power"]) - defense + random.randint(-2, 3))
        heal = int(damage * skill.get("lifesteal_pct", 0.3))
        if is_player:
            if combat["defending"]:
                damage //= 2
            combat["monster_hp"] -= damage
            combat["player_hp"] = min(combat["player_max_hp"], combat["player_hp"] + heal)
            log.append(f"[第{combat['round']}回合] 你施展【{skill_name}】，造成 {damage} 伤害并吸取 {heal} 气血！")
            if combat["monster_hp"] <= 0:
                log.append(f"{combat['monster']['name']}哀鸣一声，倒地不起！")
        else:
            if combat["defending"]:
                damage //= 2
            combat["player_hp"] -= damage
            combat["monster_hp"] = min(combat["monster_max_hp"], combat["monster_hp"] + heal)
            log.append(f"[第{combat['round']}回合] {attacker_name}施展【{skill_name}】，你受到 {damage} 伤害并被吸取 {heal} 气血！")

    if skill.get("debuff"):
        debuff = skill["debuff"]
        duration = debuff.get("rounds", 2)
        stat = "atk" if "atk" in debuff.get("target", "") else "def"
        target_debuffs = combat["monster_debuffs"] if is_player else combat["player_debuffs"]
        target_debuffs[stat] = {"mult": debuff["mult"], "rounds": duration}

    return log


def calc_damage(combat, is_player_attacker):
    """Calculate a normal attack with the legacy random damage spread."""
    attack = effective_atk(combat, is_player=is_player_attacker)
    defense = effective_def(combat, is_player=not is_player_attacker)
    return max(1, attack - defense + random.randint(-2, 3))
