"""仙途游戏修炼/挂机系统纯业务逻辑"""

import random
from datetime import datetime, timezone

from game_data import (
    IDLE_EXP_PER_SEC, IDLE_MAX_HOURS,
)
from game.utils import get_exp_needed, get_cultivation_mult, calc_level_stats


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
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    max_sec = IDLE_MAX_HOURS * 3600
    elapsed = min(elapsed, max_sec)
    if elapsed < 10:
        return 0, 0
    mult = get_cultivation_mult(char)
    gain = int(IDLE_EXP_PER_SEC * elapsed * mult)
    if get_exp_needed(char["level"]) == "-":
        gain = 0
    return max(0, gain), int(elapsed)


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
