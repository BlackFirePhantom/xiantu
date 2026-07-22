import models
import game_state
from game.secret_realm_team import create_team, reset_teams
from services.secret_realm import build_secret_realm_state, execute_secret_realm_challenge


def test_secret_realm_state_projection_is_transport_independent(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm_service.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'tester', 'unused')")
        conn.execute(
            """INSERT INTO characters
               (user_id, name, hp, max_hp, mp, max_mp, techniques, location)
               VALUES (1, 'tester', 90, 100, 40, 50, '[\"modao_rumen\"]', 'chiyan_forest')"""
        )
    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()

    try:
        create_team(1)
        game_state.get_cached_character(1)

        state = build_secret_realm_state(1, "2026-W29")

        assert state["week_id"] == "2026-W29"
        assert state["player"] == {"hp": 90, "max_hp": 100, "mp": 40, "max_mp": 50}
        assert state["team"]["members"] == [{"id": 1, "name": "tester"}]
        assert any(skill["tech_id"] == "modao_rumen" for skill in state["skills"])
    finally:
        reset_teams()
        with game_state.cache_lock:
            game_state.character_cache.clear()
            game_state.dirty_users.clear()


def test_secret_realm_service_rejects_invalid_actions_with_standard_ack(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm_action_service.db"))
    models.init_db()
    with models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'tester', 'unused')")
        conn.execute("INSERT INTO characters (user_id, name) VALUES (1, 'tester')")
    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()
    game_state.get_cached_character(1)

    outcome = execute_secret_realm_challenge(
        1,
        "2026-W29",
        {"action": "dance", "action_id": "realm-action-invalid"},
    )

    assert outcome.ack.to_dict() == {
        "ok": False,
        "reason": "invalid_action",
        "action_id": "realm-action-invalid",
    }
    assert outcome.user_message == {"text": "无效的秘境行动。", "type": "error"}
