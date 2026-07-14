"""仙途游戏核心工具函数"""

import random
import json
from game_data import (
    REALMS, SPIRIT_ROOTS, TECHNIQUES, MERIDIANS, EXP_PER_LEVEL, MAX_LEVEL,
    ITEMS, PET_BATTLE_RATIO,
    TECHNIQUE_MAX_PROFICIENCY, TECHNIQUE_PROFICIENCY_TIERS, TECHNIQUE_MEDITATE_PROFICIENCY,
    realm_name, lookup_item,
)
from npc_data import SECT_RANKS, get_sect_rank


def calc_level_stats(level):
    """计算等级对应的基础属性"""
    return {
        "max_hp": 100 + (level - 1) * 15,
        "atk": 10 + (level - 1) * 3,
        "def_stat": 5 + (level - 1) * 2,
    }


def calc_max_mp(level):
    """计算等级对应的最大灵力值"""
    return 50 + (level - 1) * 5


def get_full_stats(char):
    """计算角色完整属性（含装备、功法、经脉、灵宠加成）"""
    base = calc_level_stats(char["level"])
    atk = base["atk"]
    defn = base["def_stat"]
    max_hp = base["max_hp"]

    # 装备加成
    w = lookup_item(char["weapon"]) if char["weapon"] else None
    if w:
        atk += w.get("atk", 0)
    a = lookup_item(char["armor"]) if char["armor"] else None
    if a:
        defn += a.get("def", 0)
    ac = lookup_item(char["accessory"]) if char["accessory"] else None
    if ac:
        atk += ac.get("atk", 0)
        defn += ac.get("def", 0)
        max_hp += ac.get("bonus_hp", 0)

    # 功法加成（受熟练度影响）
    prof = get_proficiency(char)
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    for tid in learned:
        if tid in TECHNIQUES:
            t = TECHNIQUES[tid]
            pm = proficiency_mult(prof.get(tid, 0))
            max_hp += int(t["bonus_hp"] * pm)
            atk += int(t["bonus_atk"] * pm)
            defn += int(t["bonus_def"] * pm)

    # 经脉加成
    opened = json.loads(char["open_meridians"]) if char["open_meridians"] else []
    for mid in opened:
        if mid in MERIDIANS:
            m = MERIDIANS[mid]
            max_hp += m["bonus_hp"]
            atk += m["bonus_atk"]
            defn += m["bonus_def"]

    # 灵宠战斗加成
    active_pet_id = char["active_pet"]
    if active_pet_id:
        pets = json.loads(char["pets"]) if char["pets"] else []
        for pet in pets:
            if pet["id"] == active_pet_id:
                from game_data import get_pet_stats
                ps = get_pet_stats(pet)
                max_hp += int(ps["hp"] * PET_BATTLE_RATIO)
                atk += int(ps["atk"] * PET_BATTLE_RATIO)
                defn += int(ps["def"] * PET_BATTLE_RATIO)
                break

    return {"atk": atk, "def": defn, "max_hp": max_hp, "max_mp": calc_max_mp(char["level"])}


def get_exp_needed(level):
    """获取升级所需修为"""
    if level >= MAX_LEVEL:
        return "-"
    return EXP_PER_LEVEL[level] if level < len(EXP_PER_LEVEL) else EXP_PER_LEVEL[-1]


def get_cultivation_mult(char):
    """获取修炼速度总倍率（灵根 × 功法 × 熟练度）"""
    mult = 1.0
    sr = char["spirit_root"]
    if sr and sr in SPIRIT_ROOTS:
        mult *= SPIRIT_ROOTS[sr]["cultivation_mult"]
    prof = get_proficiency(char)
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    for tid in learned:
        if tid in TECHNIQUES:
            pm = proficiency_mult(prof.get(tid, 0))
            mult += TECHNIQUES[tid]["bonus_exp_pct"] * pm
    # 饰品修炼加成
    ac = lookup_item(char["accessory"]) if char["accessory"] else None
    if ac:
        mult += ac.get("bonus_exp_pct", 0)
    # 宗门贡献修炼加成
    sect_rank = get_sect_rank(char["sect_contrib"] if char["sect_contrib"] else 0)
    mult += SECT_RANKS[sect_rank]["bonus"]
    return mult


def format_duration(seconds):
    """格式化时间长度"""
    if seconds < 60:
        return f"{seconds}秒"
    if seconds < 3600:
        return f"{seconds // 60}分钟"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}小时{m}分钟" if m else f"{h}小时"


# ═══════════════ 熟练度系统 ═══════════════

def get_proficiency(char):
    return json.loads(char["proficiency"]) if char["proficiency"] else {}


def proficiency_mult(prof_val):
    """熟练度→加成倍率：0熟练度=50%效果，满熟练度=100%效果"""
    pct = prof_val / TECHNIQUE_MAX_PROFICIENCY
    return 0.5 + 0.5 * pct


def gain_proficiency(char, uid, source="fight"):
    """给所有已学功法增加熟练度，返回 {tech_id: gained} 字典"""
    from game_state import update_cached_character
    learned = json.loads(char["techniques"]) if char["techniques"] else []
    if not learned:
        return {}
    prof = get_proficiency(char)
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
        else:
            amount = TECHNIQUE_MEDITATE_PROFICIENCY
        new_val = min(TECHNIQUE_MAX_PROFICIENCY, cur + amount)
        prof[tid] = new_val
        gained[tid] = amount
    if gained:
        update_cached_character(uid, proficiency=json.dumps(prof))
    return gained
