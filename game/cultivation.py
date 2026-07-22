"""仙途游戏修炼/挂机系统纯业务逻辑"""

import random
from datetime import datetime, timezone

from game_data import (
    IDLE_EXP_PER_SEC, IDLE_MAX_HOURS,
)
from game.utils import get_exp_needed, get_cultivation_mult, calc_level_stats

# 挂机掉落模拟参数（离线与在线 AFK 共享，保证两条路径行为一致）
_DROP_INTERVAL = 60       # 每隔 60 秒尝试一次掉落（与 config.AFK_INTERVAL 对齐）
_DROP_CHANCE = 0.3        # 每次尝试 30% 概率掉落一个材料
_DROP_POOL = ("lingcao", "yaogu", "yaopimo", "hantie_kuang")
_MAX_DROP_ATTEMPTS = 150  # 防止超长挂机时循环过大


def compute_idle_reward(char, elapsed_seconds):
    """计算挂机收益：修为、材料掉落、是否安全区回血。

    离线（``process_offline_cultivation``）与在线 AFK
    （``game_state._settle_afk_reward``）共享此函数，确保两条路径产出一致。

    Args:
        char: 角色数据字典（需含 level、location、spirit_root 等字段）。
        elapsed_seconds: 自上次活动以来的秒数（将钳制到 ``IDLE_MAX_HOURS``）。

    Returns:
        dict: ``{exp: int, drops: list[str], heal_to_full: bool, elapsed: int}``
    """
    from game_data import LOCATIONS

    max_sec = IDLE_MAX_HOURS * 3600
    elapsed = min(max(0, elapsed_seconds), max_sec)

    mult = get_cultivation_mult(char)
    exp_gain = int(IDLE_EXP_PER_SEC * elapsed * mult)

    loc = LOCATIONS.get(char.get("location", "qingyun_town"), LOCATIONS["qingyun_town"])
    drops = []
    if not loc["safe"]:
        attempts = min(_MAX_DROP_ATTEMPTS, int(elapsed / _DROP_INTERVAL))
        for _ in range(attempts):
            if random.random() < _DROP_CHANCE:
                drops.append(random.choice(_DROP_POOL))

    heal_to_full = loc["safe"]

    if get_exp_needed(char["level"]) == "-":
        exp_gain = 0

    return {
        "exp": max(0, exp_gain),
        "drops": drops,
        "heal_to_full": heal_to_full,
        "elapsed": int(elapsed),
    }


def process_offline_cultivation(char):
    """计算离线挂机修为收益。

    根据角色 last_active 与当前时间的差值，计算可获得的修为、材料掉落
    及安全区回血标记。离线时长被钳制到 ``IDLE_MAX_HOURS`` 小时以内，
    不足 10 秒则不结算。已满级的角色不获得修为但仍获掉落。

    Args:
        char: 角色数据字典，需包含 last_active、level、spirit_root 等字段。

    Returns:
        dict: ``{exp: int, drops: list[str], heal_to_full: bool, elapsed: int}``。
        无需结算时返回零值字典。
    """
    _zero = {"exp": 0, "drops": [], "heal_to_full": False, "elapsed": 0}
    if not char["last_active"]:
        return _zero
    try:
        last = datetime.fromisoformat(char["last_active"])
    except (ValueError, TypeError):
        return _zero
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed_raw = (datetime.now(timezone.utc) - last).total_seconds()
    if elapsed_raw < 10:
        return _zero
    return compute_idle_reward(char, elapsed_raw)


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
