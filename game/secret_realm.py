"""Weekly secret-realm rules, kept independent from storage and Socket.IO."""

EXPLORATION_LIMIT = 3
BOSS_MAX_HP = 500
EXPLORATION_CONTRIBUTION = 5

SEASON_MODIFIERS = (
    {
        "id": "spirit_tide",
        "name": "灵潮涌动",
        "description": "秘境灵气充盈，探索额外获得灵石。",
        "gold_bonus": 4,
        "contribution_bonus": 0,
        "boss_damage_multiplier": 1,
    },
    {
        "id": "sect_rally",
        "name": "同门共鸣",
        "description": "同门战意高涨，探索额外获得宗门贡献。",
        "gold_bonus": 0,
        "contribution_bonus": 3,
        "boss_damage_multiplier": 1,
    },
    {
        "id": "flame_break",
        "name": "赤焰裂隙",
        "description": "首领护体松动，对首领造成的伤害提升 25%。",
        "gold_bonus": 0,
        "contribution_bonus": 0,
        "boss_damage_multiplier": 1.25,
    },
)


def get_season_modifier(week_id):
    """Return one stable, player-independent modifier for a weekly rotation."""
    return dict(SEASON_MODIFIERS[sum(map(ord, week_id)) % len(SEASON_MODIFIERS)])


def new_run(explorations=0, contribution=0, boss_damage=0):
    """Build the mutable per-player state for the current weekly realm."""
    return {
        "explorations": explorations,
        "contribution": contribution,
        "boss_damage": boss_damage,
    }


def explore(run, roll, *, gold_bonus=0, contribution_bonus=0):
    """Resolve one exploration and return rewards without mutating storage."""
    if run["explorations"] >= EXPLORATION_LIMIT:
        return {"ok": False, "reason": "exploration_limit"}

    updated_run = dict(run)
    updated_run["explorations"] += 1
    contribution_gain = EXPLORATION_CONTRIBUTION + contribution_bonus
    updated_run["contribution"] += contribution_gain
    gold_gain = 8 + roll + gold_bonus
    return {
        "ok": True,
        "run": updated_run,
        "gold_gain": gold_gain,
        "contribution_gain": contribution_gain,
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
