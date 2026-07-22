"""Persisted party lobbies for the weekly secret realm."""

from secrets import token_hex

from models import (
    create_secret_realm_team,
    get_secret_realm_team,
    get_secret_realm_team_for_user,
    join_secret_realm_team,
    leave_secret_realm_team,
    reset_secret_realm_teams,
)


MAX_TEAM_SIZE = 4

def create_team(user_id):
    """Create a one-person team, moving the user out of any old team."""
    while True:
        team_id = token_hex(3).upper()
        team = create_secret_realm_team(team_id, user_id)
        if team:
            return team


def join_team(user_id, team_id):
    """Join a lobby by its short code, without requiring a full party."""
    if not isinstance(team_id, str):
        return {"ok": False, "reason": "team_not_found"}
    team_id = team_id.strip().upper()
    return join_secret_realm_team(team_id, user_id, max_members=MAX_TEAM_SIZE)


def leave_team(user_id):
    return leave_secret_realm_team(user_id)


def get_team_for_user(user_id):
    return get_secret_realm_team_for_user(user_id)


def get_team(team_id):
    return get_secret_realm_team(str(team_id).strip().upper())


def reset_teams():
    """Clear all persisted lobbies; used by isolated tests."""
    reset_secret_realm_teams()
