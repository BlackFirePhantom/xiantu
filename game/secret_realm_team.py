"""In-memory party lobbies for the weekly secret realm.

Teams are intentionally ephemeral: a lobby belongs to the connected game
session and is recreated when the player starts another run or reconnects.
The boss and entry settlement remain persisted in the database.
"""

from secrets import token_hex
from threading import RLock


MAX_TEAM_SIZE = 4

_lock = RLock()
_teams = {}
_user_teams = {}


def _view(team):
    return {
        "id": team["id"],
        "leader_id": team["leader_id"],
        "members": list(team["members"]),
    }


def _remove_member_locked(user_id):
    team_id = _user_teams.pop(user_id, None)
    if not team_id:
        return None
    team = _teams.get(team_id)
    if not team:
        return None
    if user_id in team["members"]:
        team["members"].remove(user_id)
    if not team["members"]:
        del _teams[team_id]
        return None
    if team["leader_id"] == user_id:
        team["leader_id"] = team["members"][0]
    return _view(team)


def create_team(user_id):
    """Create a one-person team, moving the user out of any old lobby."""
    with _lock:
        _remove_member_locked(user_id)
        team_id = token_hex(3).upper()
        while team_id in _teams:
            team_id = token_hex(3).upper()
        team = {"id": team_id, "leader_id": user_id, "members": [user_id]}
        _teams[team_id] = team
        _user_teams[user_id] = team_id
        return _view(team)


def join_team(user_id, team_id):
    """Join a lobby by its short code, without requiring a full party."""
    if not isinstance(team_id, str):
        return {"ok": False, "reason": "team_not_found"}
    team_id = team_id.strip().upper()
    with _lock:
        team = _teams.get(team_id)
        if not team:
            return {"ok": False, "reason": "team_not_found"}
        if _user_teams.get(user_id) == team_id:
            return _view(team)
        if len(team["members"]) >= MAX_TEAM_SIZE:
            return {"ok": False, "reason": "team_full"}
        _remove_member_locked(user_id)
        team["members"].append(user_id)
        _user_teams[user_id] = team_id
        return _view(team)


def leave_team(user_id):
    with _lock:
        return _remove_member_locked(user_id)


def get_team_for_user(user_id):
    with _lock:
        team_id = _user_teams.get(user_id)
        team = _teams.get(team_id) if team_id else None
        return _view(team) if team else None


def get_team(team_id):
    with _lock:
        team = _teams.get(str(team_id).strip().upper())
        return _view(team) if team else None


def reset_teams():
    """Clear all lobbies; used by tests and process-level maintenance."""
    with _lock:
        _teams.clear()
        _user_teams.clear()
