"""仙途游戏修炼/挂机系统纯业务逻辑"""

import random
from datetime import datetime

from game_data import (
    ITEMS, LOCATIONS, BREAKTHROUGH_CHANCE, MAX_LEVEL,
    IDLE_EXP_PER_SEC, IDLE_MAX_HOURS,
)
from game.utils import get_full_stats, get_exp_needed, get_cultivation_mult, calc_level_stats


# AFK 挂机材料掉落池
AFK_DROP_POOL = ["lingcao", "yaogu", "yaopimo", "hantie_kuang"]

# AFK 挂机材料掉落概率
AFK_DROP_CHANCE = 0.3


def process_offline_cultivation(char):
    """计算离线挂机修为收益。

    根据角色 last_active 与当前时间的差值，计算可获得的修为。
    离线时长被钳制到 IDLE_MAX_HOURS 小时以内，不足 10 秒则不结算。
    已满级的角色不获得修为。

    Args:
        char: 角色数据字典，需包含 last_active、level、spirit_root 等字段。

    Returns:
        (gain, elapsed_seconds): 获得的修为值（int）和经过的秒数（int）。
    """
    if not char["last_active"]:
        return 0, 0
    try:
        last = datetime.fromisoformat(char["last_active"])
    except (ValueError, TypeError):
        return 0, 0
    elapsed = (datetime.utcnow() - last).total_seconds()
    max_sec = IDLE_MAX_HOURS * 3600
    elapsed = min(elapsed, max_sec)
    if elapsed < 10:
        return 0, 0
    mult = get_cultivation_mult(char)
    gain = int(IDLE_EXP_PER_SEC * elapsed * mult)
    if get_exp_needed(char["level"]) == "-":
        gain = 0
    return max(0, gain), int(elapsed)


def process_afk_tick(char, loc, now, afk_start_time, afk_max_hours, afk_interval, idle_exp_per_sec):
    """处理一次在线挂机 tick。

    计算挂机时长（钳制到最大值），发放修为经验，并在非安全区域概率
    掉落材料。返回的字典包含经验收益、掉落列表和格式化的持续时间。

    Args:
        char: 角色数据字典。
        loc: 当前地点数据字典（需包含 "safe" 字段）。
        now: 当前时间戳（time.time()）。
        afk_start_time: 挂机开始时间戳。
        afk_max_hours: 挂机最大时长（小时）。
        afk_interval: 挂机结算间隔（秒）。
        idle_exp_per_sec: 每秒基础修为收益。

    Returns:
        dict: {
            "exp_gain": int,           # 本次 tick 获得的修为
            "drops": list[str],        # 掉落的物品 id 列表
            "duration": int,           # 挂机总时长（秒）
            "max_hp_regen": bool,      # 安全区是否触发满血回复
        }
    """
    afk_duration = now - afk_start_time
    max_duration = afk_max_hours * 3600

    if afk_duration > max_duration:
        afk_duration = max_duration

    if afk_duration < afk_interval:
        return {"exp_gain": 0, "drops": [], "duration": int(afk_duration), "max_hp_regen": False}

    mult = get_cultivation_mult(char)
    exp_gain = int(idle_exp_per_sec * afk_interval * mult)

    # 挂机地点有怪物时，概率掉落材料
    drops = []
    if not loc["safe"] and random.random() < AFK_DROP_CHANCE:
        drops.append(random.choice(AFK_DROP_POOL))

    # 已满级不获得修为
    if get_exp_needed(char["level"]) == "-":
        exp_gain = 0

    # 安全区域自动回满血
    max_hp_regen = False
    if loc["safe"]:
        stats = get_full_stats(char)
        if char["hp"] < stats["max_hp"]:
            max_hp_regen = True

    return {
        "exp_gain": exp_gain,
        "drops": drops,
        "duration": int(afk_duration),
        "max_hp_regen": max_hp_regen,
    }


def attempt_breakthrough(char, exp_needed, breakthrough_chance):
    """尝试境界突破。

    根据给定概率判定突破是否成功。成功时提升等级并回满血；失败时
    损失当前血量的 1/3（最低保留 1 点）。

    Args:
        char: 角色数据字典，需包含 level、hp 字段。
        exp_needed: 本次突破消耗的修为值（由调用方扣减）。
        breakthrough_chance: 突破成功概率（0.0 ~ 1.0）。

    Returns:
        dict: {
            "success": bool,           # 是否突破成功
            "hp_loss": int,            # 失败时损失的血量（成功时为 0）
            "new_level": int,          # 成功时的新等级（失败时不变）
            "new_stats": dict | None,  # 成功时的新基础属性（失败时为 None）
        }
    """
    if random.random() < breakthrough_chance:
        new_level = char["level"] + 1
        new_stats = calc_level_stats(new_level)
        return {
            "success": True,
            "hp_loss": 0,
            "new_level": new_level,
            "new_stats": new_stats,
        }
    else:
        hp_loss = char["hp"] // 3
        return {
            "success": False,
            "hp_loss": hp_loss,
            "new_level": char["level"],
            "new_stats": None,
        }
