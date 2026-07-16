"""Weekly secret-realm rules, kept independent from storage and Socket.IO."""

EXPLORATION_LIMIT = 3
BOSS_MAX_HP = 500
EXPLORATION_CONTRIBUTION = 5


def new_run(explorations=0, contribution=0, boss_damage=0):
    """Build the mutable per-player state for the current weekly realm."""
    return {
        "explorations": explorations,
        "contribution": contribution,
        "boss_damage": boss_damage,
    }


def explore(run, roll):
    """Resolve one exploration and return rewards without mutating storage."""
    if run["explorations"] >= EXPLORATION_LIMIT:
        return {"ok": False, "reason": "exploration_limit"}

    updated_run = dict(run)
    updated_run["explorations"] += 1
    updated_run["contribution"] += EXPLORATION_CONTRIBUTION
    gold_gain = 8 + roll
    return {
        "ok": True,
        "run": updated_run,
        "gold_gain": gold_gain,
        "contribution_gain": EXPLORATION_CONTRIBUTION,
        "boss_unlocked": updated_run["explorations"] >= EXPLORATION_LIMIT,
    }


def challenge_boss(run, boss_hp, damage):
    """Apply one player's damage to the shared boss after the exploration gate."""
    if run["explorations"] < EXPLORATION_LIMIT:
        return {"ok": False, "reason": "boss_locked"}
    if boss_hp <= 0:
        return {"ok": False, "reason": "boss_defeated"}

    dealt = min(max(1, damage), boss_hp)
    updated_run = dict(run)
    updated_run["boss_damage"] += dealt
    updated_run["contribution"] += dealt
    remaining_hp = boss_hp - dealt
    defeated = remaining_hp == 0
    return {
        "ok": True,
        "run": updated_run,
        "damage": dealt,
        "boss_hp": remaining_hp,
        "defeated": defeated,
        "reward_item": "chiyan_jing" if defeated else None,
    }
