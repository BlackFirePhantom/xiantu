from game.secret_realm import (
    BOSS_MAX_HP,
    EXPLORATION_LIMIT,
    WEEKLY_BOSSES,
    challenge_boss,
    explore,
    get_weekly_boss,
    new_run,
)
import models
import game_state
from game.secret_realm_team import reset_teams


def test_exploration_grants_progress_gold_and_contribution():
    result = explore(new_run(), roll=3)

    assert result["ok"] is True
    assert result["run"]["explorations"] == 1
    assert result["gold_gain"] == 11
    assert result["contribution_gain"] == 5
    assert result["boss_unlocked"] is False


def test_third_exploration_uses_the_last_realm_entry():
    run = new_run(explorations=EXPLORATION_LIMIT - 1)

    result = explore(run, roll=0)

    assert result["ok"] is True
    assert result["run"]["explorations"] == EXPLORATION_LIMIT
    assert result["boss_unlocked"] is True


def test_exploration_limit_prevents_extra_rewards():
    result = explore(new_run(explorations=EXPLORATION_LIMIT), roll=5)

    assert result == {"ok": False, "reason": "exploration_limit"}


def test_boss_requires_a_remaining_realm_entry():
    result = challenge_boss(new_run(explorations=EXPLORATION_LIMIT), boss_hp=BOSS_MAX_HP, damage=50)

    assert result == {"ok": False, "reason": "no_entries"}


def test_boss_damage_consumes_an_entry_and_defeat_rewards_crystal():
    run = new_run(contribution=15)

    result = challenge_boss(run, boss_hp=40, damage=50)

    assert result["ok"] is True
    assert result["boss_hp"] == 0
    assert result["damage"] == 40
    assert result["defeated"] is True
    assert result["reward_item"] == "chiyan_jing"
    assert result["run"]["contribution"] == 55
    assert result["run"]["explorations"] == 1


def test_weekly_boss_rotation_is_stable_and_exposes_multiple_bosses():
    first_week = get_weekly_boss("2026-W01")

    assert first_week == get_weekly_boss("2026-W01")
    assert {get_weekly_boss(f"2026-W{week:02d}")["id"] for week in range(1, 9)} == {
        boss["id"] for boss in WEEKLY_BOSSES
    }
    assert {"name", "description", "max_hp", "attack"} <= first_week.keys()


def test_boss_encounter_keeps_entry_until_death_or_kill(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm_encounter.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'tester', 'unused')")
        conn.execute(
            "INSERT INTO characters (user_id, name, hp, max_hp, location) VALUES (1, 'tester', 100, 100, 'chiyan_forest')"
        )

    result = models.resolve_secret_realm_boss_encounter(
        1, "2026-W29", player_damage=40, player_defense=5, boss_attack=25, max_hp=100, entry_limit=3
    )

    assert result["ok"] is True
    assert result["damage"] == 40
    assert result["boss_hp"] == 60
    assert result["player_damage"] == 20
    assert result["player_hp"] == 80
    assert result["entry_consumed"] is False
    assert result["entries_remaining"] == EXPLORATION_LIMIT
    assert models.get_secret_realm_run(1, "2026-W29")["explorations"] == 0
    assert models.get_character(1)["hp"] == 80


def test_boss_encounter_persists_skill_updated_hp_and_mp(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm_skill.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'tester', 'unused')")
        conn.execute(
            "INSERT INTO characters (user_id, name, hp, max_hp, mp, max_mp, location) VALUES (1, 'tester', 100, 100, 50, 80, 'chiyan_forest')"
        )

    result = models.resolve_secret_realm_boss_encounter(
        1, "2026-W29", player_damage=20, player_defense=5, boss_attack=25,
        max_hp=100, entry_limit=3, player_hp=90, player_mp=35
    )

    assert result["player_hp"] == 70
    assert result["player_mp"] == 35
    assert models.get_character(1)["mp"] == 35

    follow_up = models.resolve_secret_realm_boss_encounter(
        1, "2026-W29", player_damage=40, player_defense=5, boss_attack=25, max_hp=100, entry_limit=3
    )
    assert follow_up["entry_consumed"] is False
    assert follow_up["entries_remaining"] == EXPLORATION_LIMIT

    finishing = models.resolve_secret_realm_boss_encounter(
        1, "2026-W29", player_damage=40, player_defense=5, boss_attack=25, max_hp=100, entry_limit=3
    )
    assert finishing["defeated"] is True
    assert finishing["entry_consumed"] is True
    assert finishing["entries_remaining"] == EXPLORATION_LIMIT - 1


def test_boss_death_returns_to_safety_and_exhausted_entries_block_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm_death.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'tester', 'unused')")
        conn.execute(
            "INSERT INTO characters (user_id, name, hp, max_hp, location) VALUES (1, 'tester', 10, 100, 'chiyan_forest')"
        )

    death = models.resolve_secret_realm_boss_encounter(
        1, "2026-W29", player_damage=10, player_defense=0, boss_attack=30, max_hp=100, entry_limit=3
    )
    character = models.get_character(1)
    models.save_secret_realm_run(1, "2026-W29", explorations=3, contribution=10, boss_damage=10)
    blocked = models.resolve_secret_realm_boss_encounter(
        1, "2026-W29", player_damage=10, player_defense=0, boss_attack=30, max_hp=100, entry_limit=3
    )

    assert death["player_died"] is True
    assert death["entries_remaining"] == 2
    assert character["hp"] == 50
    assert character["deaths"] == 1
    assert character["location"] == "qingyun_town"
    assert blocked == {"ok": False, "reason": "no_entries"}


def test_secret_realm_socket_state_shows_player_hp_and_consumes_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm_socket.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'tester', 'unused')")
        conn.execute(
            "INSERT INTO characters (user_id, name, hp, max_hp, mp, techniques, location) VALUES (1, 'tester', 100, 100, 50, '[\"modao_rumen\"]', 'chiyan_forest')"
        )
    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()

    import handlers.secret_realm as realm_handlers
    monkeypatch.setattr(realm_handlers, "_week_id", lambda: "2026-W29")
    from app import app, socketio

    try:
        flask_client = app.test_client()
        with flask_client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "tester"
        client = socketio.test_client(app, flask_test_client=flask_client)
        client.emit("get_secret_realm")
        initial = [event["args"][0] for event in client.get_received() if event["name"] == "secret_realm_state"][0]

        client.emit("secret_realm_challenge", {"action": "skill", "skill_id": "modao_rumen"})
        updated = [event["args"][0] for event in client.get_received() if event["name"] == "secret_realm_state"][-1]

        assert initial["boss"]["name"] == get_weekly_boss("2026-W29")["name"]
        assert initial["player"]["hp"] == 100
        assert initial["player"]["mp"] == 50
        assert any(skill["tech_id"] == "modao_rumen" for skill in initial["skills"])
        assert initial["entries_remaining"] == EXPLORATION_LIMIT
        assert updated["entries_remaining"] == EXPLORATION_LIMIT
        assert updated["player"]["hp"] < initial["player"]["hp"]
        assert updated["player"]["mp"] < initial["player"]["mp"]
        assert updated["team"]["members"] == [{"id": 1, "name": "tester"}]
        client.disconnect()
    finally:
        reset_teams()
        with game_state.cache_lock:
            game_state.character_cache.clear()
            game_state.dirty_users.clear()


def test_secret_realm_challenge_returns_error_state_when_settlement_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm_socket_error.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'tester', 'unused')")
        conn.execute(
            "INSERT INTO characters (user_id, name, hp, max_hp, location) VALUES (1, 'tester', 100, 100, 'chiyan_forest')"
        )

    import handlers.secret_realm as realm_handlers
    monkeypatch.setattr(realm_handlers, "_week_id", lambda: "2026-W29")
    monkeypatch.setattr(
        realm_handlers,
        "resolve_secret_realm_boss_encounter",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    from app import app, socketio

    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()
    try:
        flask_client = app.test_client()
        with flask_client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "tester"
        client = socketio.test_client(app, flask_test_client=flask_client)
        client.emit("secret_realm_challenge")
        received = client.get_received()

        messages = [event["args"][0] for event in received if event["name"] == "game_msg"]
        states = [event["args"][0] for event in received if event["name"] == "secret_realm_state"]
        assert messages[-1]["text"] == "秘境结算失败，请稍后重试。"
        assert states[-1]["entries_remaining"] == EXPLORATION_LIMIT
        client.disconnect()
    finally:
        reset_teams()
        with game_state.cache_lock:
            game_state.character_cache.clear()
            game_state.dirty_users.clear()


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


def test_refresh_cached_character_reflects_atomic_settlement_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'tester', 'unused')")
        conn.execute("INSERT INTO characters (user_id, name) VALUES (1, 'tester')")
    models.save_secret_realm_run(1, "2026-W28", explorations=3, contribution=80, boss_damage=70)
    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()
    try:
        assert game_state.get_cached_character(1)["gold"] == 50
        assert models.claim_secret_realm_settlement(1, "2026-W28")["ok"] is True

        refreshed = game_state.refresh_cached_character(1)

        assert refreshed["gold"] == 120
        assert game_state.get_cached_character(1)["gold"] == 120
        assert 1 not in game_state.dirty_users
    finally:
        with game_state.cache_lock:
            game_state.character_cache.clear()
            game_state.dirty_users.clear()


def test_team_coop_combat_buffs_and_resonance(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm_team.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'p1', 'unused')")
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (2, 'p2', 'unused')")
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (3, 'p3', 'unused')")
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (4, 'p4', 'unused')")
        conn.execute("INSERT INTO characters (user_id, name, hp, max_hp, spirit_root, location) VALUES (1, 'p1', 100, 100, 'jin', 'chiyan_forest')")
        conn.execute("INSERT INTO characters (user_id, name, hp, max_hp, spirit_root, location) VALUES (2, 'p2', 100, 100, 'mu', 'chiyan_forest')")
        conn.execute("INSERT INTO characters (user_id, name, hp, max_hp, spirit_root, location) VALUES (3, 'p3', 100, 100, 'shui', 'chiyan_forest')")
        conn.execute("INSERT INTO characters (user_id, name, hp, max_hp, spirit_root, location) VALUES (4, 'p4', 100, 100, 'huo', 'chiyan_forest')")

    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()

    import handlers.secret_realm as realm_handlers
    monkeypatch.setattr(realm_handlers, "_week_id", lambda: "2026-W29")
    from app import app, socketio
    from game.secret_realm_team import create_team, join_team, reset_teams

    try:
        team = create_team(1)
        join_team(2, team["id"])
        join_team(3, team["id"])
        join_team(4, team["id"])

        flask_client = app.test_client()
        with flask_client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "p1"

        client = socketio.test_client(app, flask_test_client=flask_client)
        client.emit("get_secret_realm")
        initial = [event["args"][0] for event in client.get_received() if event["name"] == "secret_realm_state"][0]

        assert initial["team"]["id"] == team["id"]
        assert len(initial["team"]["members"]) == 4

        client.emit("secret_realm_challenge", {"action": "attack"})
        received = client.get_received()

        messages = [event["args"][0] for event in received if event["name"] == "game_msg"]

        fight_msg = [m for m in messages if m["type"] == "fight"]
        assert len(fight_msg) > 0
        text = fight_msg[0]["text"]

        assert "队伍共 4 人" in text
        assert "四象乾坤" in text

        client.disconnect()
    finally:
        reset_teams()
        with game_state.cache_lock:
            game_state.character_cache.clear()
            game_state.dirty_users.clear()
