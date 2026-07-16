from game.secret_realm import (
    BOSS_MAX_HP,
    EXPLORATION_LIMIT,
    challenge_boss,
    explore,
    new_run,
)
import models


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


def test_secret_realm_records_are_isolated_by_week_and_share_one_boss(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            (7, "realm_tester", "unused"),
        )

    first_run = models.get_secret_realm_run(7, "2026-W29")
    models.save_secret_realm_run(7, "2026-W29", explorations=3, contribution=50, boss_damage=35)
    same_week_run = models.get_secret_realm_run(7, "2026-W29")
    next_week_run = models.get_secret_realm_run(7, "2026-W30")

    first_boss = models.get_secret_realm_boss("2026-W29")
    models.save_secret_realm_boss("2026-W29", hp=321)
    same_week_boss = models.get_secret_realm_boss("2026-W29")

    assert first_run == {"explorations": 0, "contribution": 0, "boss_damage": 0}
    assert same_week_run == {"explorations": 3, "contribution": 50, "boss_damage": 35}
    assert next_week_run == {"explorations": 0, "contribution": 0, "boss_damage": 0}
    assert first_boss["hp"] == BOSS_MAX_HP
    assert same_week_boss["hp"] == 321
