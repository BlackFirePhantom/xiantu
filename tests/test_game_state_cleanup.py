import time

import game_state
import models


def test_stale_combat_cleanup_persists_current_hp_immediately(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "stale_combat.db"))
    models.init_db()
    with models.get_db() as connection:
        connection.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (1, 'stale-user', 'unused')"
        )
        connection.execute(
            "INSERT INTO characters (user_id, name, hp) VALUES (1, 'stale-char', 100)"
        )

    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()
    game_state.get_cached_character(1)
    with game_state.combat_lock:
        game_state.active_combats[1] = {
            "player_hp": 41,
            "last_action_at": time.time() - game_state.COMBAT_TIMEOUT - 1,
            "username": "stale-user",
        }

    try:
        game_state.cleanup_stale_combats()

        assert 1 not in game_state.active_combats
        assert models.get_character(1)["hp"] == 41
        assert 1 not in game_state.dirty_users
    finally:
        with game_state.combat_lock:
            game_state.active_combats.clear()
        with game_state.cache_lock:
            game_state.character_cache.clear()
            game_state.dirty_users.clear()
