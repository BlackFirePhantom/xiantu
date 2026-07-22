import importlib
from concurrent.futures import ThreadPoolExecutor

import models
import pytest
import game.secret_realm_team as team_module
from game.secret_realm_team import (
    MAX_TEAM_SIZE,
    create_team,
    get_team_for_user,
    join_team,
    leave_team,
    reset_teams,
)


@pytest.fixture(autouse=True)
def isolated_team_database(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "realm_teams.db"))
    models.init_db()
    with models.get_db() as conn:
        for user_id in range(1, 21):
            conn.execute(
                "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'unused')",
                (user_id, f"team-user-{user_id}"),
            )
    reset_teams()
    yield
    reset_teams()


def test_realm_team_can_start_solo_and_fill_to_four_members():
    reset_teams()
    try:
        team = create_team(1)
        assert team["leader_id"] == 1
        assert team["members"] == [1]

        for user_id in (2, 3, 4):
            joined = join_team(user_id, team["id"])
            assert joined["members"][-1] == user_id

        assert len(get_team_for_user(1)["members"]) == MAX_TEAM_SIZE
        assert join_team(5, team["id"]) == {"ok": False, "reason": "team_full"}
    finally:
        reset_teams()


def test_leaving_team_reassigns_leader_and_removes_empty_team():
    reset_teams()
    try:
        team = create_team(10)
        join_team(11, team["id"])
        assert leave_team(10)["leader_id"] == 11
        assert leave_team(11) is None
        assert get_team_for_user(11) is None
    finally:
        reset_teams()


def test_team_survives_module_reload():
    team = team_module.create_team(1)
    team_module.join_team(2, team["id"])

    reloaded = importlib.reload(team_module)

    assert reloaded.get_team_for_user(1) == {
        "id": team["id"],
        "leader_id": 1,
        "members": [1, 2],
    }
    assert reloaded.get_team(team["id"])["members"] == [1, 2]


def test_concurrent_joins_never_exceed_four_members():
    team = create_team(1)

    with ThreadPoolExecutor(max_workers=7) as executor:
        results = list(executor.map(lambda user_id: join_team(user_id, team["id"]), range(2, 9)))

    persisted = get_team_for_user(1)
    successful = [result for result in results if result.get("ok") is not False]
    rejected = [result for result in results if result.get("reason") == "team_full"]
    assert len(persisted["members"]) == MAX_TEAM_SIZE
    assert len(set(persisted["members"])) == MAX_TEAM_SIZE
    assert len(successful) == MAX_TEAM_SIZE - 1
    assert len(rejected) == 4


def test_failed_join_keeps_player_in_their_existing_team():
    full_team = create_team(1)
    for user_id in (2, 3, 4):
        join_team(user_id, full_team["id"])
    existing_team = create_team(10)

    result = join_team(10, full_team["id"])

    assert result == {"ok": False, "reason": "team_full"}
    assert get_team_for_user(10)["id"] == existing_team["id"]
