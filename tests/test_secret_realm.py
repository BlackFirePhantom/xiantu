from game.secret_realm import (
    BOSS_MAX_HP,
    EXPLORATION_LIMIT,
    challenge_boss,
    explore,
    new_run,
)


def test_exploration_grants_progress_gold_and_contribution():
    result = explore(new_run(), roll=3)

    assert result["ok"] is True
    assert result["run"]["explorations"] == 1
    assert result["gold_gain"] == 11
    assert result["contribution_gain"] == 5
    assert result["boss_unlocked"] is False


def test_third_exploration_unlocks_the_realm_boss():
    run = new_run(explorations=EXPLORATION_LIMIT - 1)

    result = explore(run, roll=0)

    assert result["ok"] is True
    assert result["run"]["explorations"] == EXPLORATION_LIMIT
    assert result["boss_unlocked"] is True


def test_exploration_limit_prevents_extra_rewards():
    result = explore(new_run(explorations=EXPLORATION_LIMIT), roll=5)

    assert result == {"ok": False, "reason": "exploration_limit"}


def test_boss_requires_the_exploration_gate():
    result = challenge_boss(new_run(), boss_hp=BOSS_MAX_HP, damage=50)

    assert result == {"ok": False, "reason": "boss_locked"}


def test_boss_damage_becomes_contribution_and_defeat_rewards_crystal():
    run = new_run(explorations=EXPLORATION_LIMIT, contribution=15)

    result = challenge_boss(run, boss_hp=40, damage=50)

    assert result["ok"] is True
    assert result["boss_hp"] == 0
    assert result["damage"] == 40
    assert result["defeated"] is True
    assert result["reward_item"] == "chiyan_jing"
    assert result["run"]["contribution"] == 55
