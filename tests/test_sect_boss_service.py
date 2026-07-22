import game_state
import models

from services.sect_boss import build_sect_boss_state, execute_sect_boss_challenge


def _seed_character(user_id, name):
    with models.get_db() as connection:
        connection.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'unused')",
            (user_id, name),
        )
        connection.execute(
            "INSERT INTO characters (user_id, name) VALUES (?, ?)",
            (user_id, name),
        )


def test_sect_boss_state_projection_is_transport_independent(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "sect_state.db"))
    models.init_db()

    state = build_sect_boss_state("2026-W30")

    assert state == {
        "schema_version": 1,
        "kind": "sect_boss",
        "week_id": "2026-W30",
        "name": "护宗魔蛟",
        "boss": {"hp": 1200, "max_hp": 1200},
        "leaderboard": [],
    }


def test_sect_boss_challenge_returns_standard_action_result(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "sect_action.db"))
    models.init_db()
    _seed_character(1, "sect_tester")
    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()

    try:
        character = game_state.get_cached_character(1)
        outcome = execute_sect_boss_challenge(1, "2026-W30", character)

        assert outcome.ack.ok is True
        assert outcome.ack.data["damage"] > 0
        assert outcome.message["type"] == "fight"
        assert build_sect_boss_state("2026-W30")["boss"]["hp"] < 1200
    finally:
        with game_state.cache_lock:
            game_state.character_cache.clear()
            game_state.dirty_users.clear()
