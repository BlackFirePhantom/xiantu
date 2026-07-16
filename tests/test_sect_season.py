import models
import game_state
from game.secret_realm import get_season_modifier


def _seed_character(user_id, name):
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'unused')", (user_id, name))
        conn.execute("INSERT INTO characters (user_id, name) VALUES (?, ?)", (user_id, name))


def test_weekly_modifier_is_deterministic_and_exposes_gameplay_effects():
    first = get_season_modifier("2026-W30")
    second = get_season_modifier("2026-W30")

    assert first == second
    assert {"id", "name", "description", "gold_bonus", "contribution_bonus", "boss_damage_multiplier"} <= first.keys()
    assert first["boss_damage_multiplier"] >= 1


def test_first_place_secret_realm_settlement_awards_a_limited_title_once(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "season.db"))
    models.init_db()
    _seed_character(1, "champion")
    models.save_secret_realm_run(1, "2026-W30", explorations=3, contribution=90, boss_damage=80)

    first_claim = models.claim_secret_realm_settlement(1, "2026-W30")
    duplicate_claim = models.claim_secret_realm_settlement(1, "2026-W30")

    assert first_claim["title_reward"] == "赤焰征服者·2026-W30"
    assert duplicate_claim == {"ok": False, "reason": "already_claimed"}
    assert models.get_character_titles(1) == ["赤焰征服者·2026-W30"]


def test_sect_boss_damage_is_shared_and_final_reward_is_only_granted_once(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "sect_boss.db"))
    models.init_db()
    _seed_character(1, "first")
    _seed_character(2, "second")

    first_hit = models.apply_sect_boss_damage(1, "2026-W30", 100, max_hp=150)
    final_hit = models.apply_sect_boss_damage(2, "2026-W30", 100, max_hp=150)
    duplicate = models.apply_sect_boss_damage(1, "2026-W30", 10, max_hp=150)

    assert first_hit == {"ok": True, "damage": 100, "boss_hp": 50, "defeated": False, "reward_granted": False}
    assert final_hit == {"ok": True, "damage": 50, "boss_hp": 0, "defeated": True, "reward_granted": True}
    assert duplicate == {"ok": False, "reason": "boss_defeated"}
    assert models.get_character_inventory(2)["zongmen_lingpai"] == 1
    assert models.get_sect_boss_leaderboard("2026-W30") == [
        {"name": "first", "damage": 100},
        {"name": "second", "damage": 50},
    ]


def test_sect_boss_socket_flow_returns_shared_state(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "sect_socket.db"))
    models.init_db()
    _seed_character(1, "socket_tester")
    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()

    from app import app, socketio

    try:
        flask_client = app.test_client()
        with flask_client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "socket_tester"
        client = socketio.test_client(app, flask_test_client=flask_client)
        client.emit("get_sect_boss")

        received = client.get_received()

        payloads = [message["args"][0] for message in received if message["name"] == "sect_boss_state"]
        assert payloads[0]["boss"] == {"hp": 1200, "max_hp": 1200}
        assert payloads[0]["leaderboard"] == []
        client.disconnect()
    finally:
        with game_state.cache_lock:
            game_state.character_cache.clear()
            game_state.dirty_users.clear()
