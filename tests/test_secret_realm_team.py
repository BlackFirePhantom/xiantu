from game.secret_realm_team import (
    MAX_TEAM_SIZE,
    create_team,
    get_team_for_user,
    join_team,
    leave_team,
    reset_teams,
)


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
