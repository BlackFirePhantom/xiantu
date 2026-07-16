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


def test_atomic_boss_settlement_awards_the_kill_once(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'tester', 'unused')")
        conn.execute("INSERT INTO characters (user_id, name) VALUES (1, 'tester')")

    first = models.apply_secret_realm_boss_damage(1, "2026-W29", 60)
    finishing = models.apply_secret_realm_boss_damage(1, "2026-W29", 600)
    duplicate = models.apply_secret_realm_boss_damage(1, "2026-W29", 10)
    character = models.get_character(1)

    assert first == {"ok": True, "damage": 60, "boss_hp": 440, "defeated": False, "reward_granted": False}
    assert finishing == {"ok": True, "damage": 440, "boss_hp": 0, "defeated": True, "reward_granted": True}
    assert duplicate == {"ok": False, "reason": "boss_defeated"}
    assert character["sect_contrib"] == 500
    assert models.get_character_inventory(1)["chiyan_jing"] == 1


def test_weekly_settlement_rewards_rank_and_can_only_be_claimed_once(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm.db"))
    models.init_db()
    with models.get_db() as conn:
        for user_id, name in ((1, "first"), (2, "second")):
            conn.execute("INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'unused')", (user_id, name))
            conn.execute("INSERT INTO characters (user_id, name) VALUES (?, ?)", (user_id, name))
    models.save_secret_realm_run(1, "2026-W28", explorations=3, contribution=80, boss_damage=70)
    models.save_secret_realm_run(2, "2026-W28", explorations=3, contribution=30, boss_damage=20)

    result = models.claim_secret_realm_settlement(2, "2026-W28")
    duplicate = models.claim_secret_realm_settlement(2, "2026-W28")

    assert result == {"ok": True, "week_id": "2026-W28", "rank": 2, "gold_reward": 50}
    assert duplicate == {"ok": False, "reason": "already_claimed"}
    assert models.get_character(2)["gold"] == 100
