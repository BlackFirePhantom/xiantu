"""Socket.IO handlers for the weekly secret realm."""

from datetime import date

from flask import session
from flask_socketio import emit, join_room, leave_room

import game_state
from game.secret_realm import EXPLORATION_LIMIT, get_season_modifier, get_weekly_boss
from game.secret_realm_team import create_team, get_team_for_user, join_team, leave_team
from game.utils import get_full_stats
from models import (
    claim_secret_realm_settlement,
    get_character,
    get_character_titles,
    get_pending_secret_realm_settlements,
    get_secret_realm_boss,
    get_secret_realm_leaderboard,
    get_secret_realm_run,
    resolve_secret_realm_boss_encounter,
)
from .base import do_get_state


def _week_id(today=None):
    iso_week = (today or date.today()).isocalendar()
    return f"{iso_week.year}-W{iso_week.week:02d}"


def _team_state(user_id):
    team = get_team_for_user(user_id)
    if not team:
        return None
    members = []
    for member_id in team["members"]:
        char = game_state.get_cached_character(member_id) or get_character(member_id)
        members.append({"id": member_id, "name": char["name"] if char else f"玩家{member_id}"})
    return {
        "id": team["id"],
        "leader_id": team["leader_id"],
        "is_leader": team["leader_id"] == user_id,
        "members": members,
        "max_members": 4,
    }


def _state_for(user_id):
    week_id = _week_id()
    run = get_secret_realm_run(user_id, week_id)
    boss_config = get_weekly_boss(week_id)
    boss = get_secret_realm_boss(week_id, max_hp=boss_config["max_hp"])
    boss.update(boss_config)
    char = game_state.get_cached_character(user_id)
    stats = get_full_stats(char) if char else {"max_hp": 0}
    return {
        "week_id": week_id,
        "name": "轮回秘境",
        "entries_remaining": max(0, EXPLORATION_LIMIT - run["explorations"]),
        "contribution": run["contribution"],
        "boss_damage": run["boss_damage"],
        "boss": boss,
        "player": {"hp": char["hp"], "max_hp": stats["max_hp"]} if char else None,
        "leaderboard": get_secret_realm_leaderboard(week_id),
        "pending_settlements": get_pending_secret_realm_settlements(user_id, week_id),
        "season": get_season_modifier(week_id),
        "titles": get_character_titles(user_id),
        "team": _team_state(user_id),
    }


def _emit_state(user_id):
    emit("secret_realm_state", _state_for(user_id))


def register_secret_realm_handlers(socketio):
    @socketio.on("get_secret_realm")
    def handle_get_secret_realm():
        if "user_id" in session:
            _emit_state(session["user_id"])

    @socketio.on("secret_realm_team_create")
    def handle_secret_realm_team_create():
        if "user_id" not in session:
            return
        user_id = session["user_id"]
        old_team = get_team_for_user(user_id)
        if old_team:
            leave_room(old_team["id"])
        team = create_team(user_id)
        join_room(team["id"])
        emit("game_msg", {"text": f"已创建秘境队伍，队伍码：{team['id']}。单人即可开启秘境。", "type": "system"})
        _emit_state(user_id)
        socketio.emit("secret_realm_team_changed", {"team_id": team["id"]}, room=team["id"])

    @socketio.on("secret_realm_team_join")
    def handle_secret_realm_team_join(data):
        if "user_id" not in session or not isinstance(data, dict):
            return
        user_id = session["user_id"]
        old_team = get_team_for_user(user_id)
        result = join_team(user_id, data.get("team_id"))
        if isinstance(result, dict) and result.get("ok") is False:
            text = "队伍不存在。" if result["reason"] == "team_not_found" else "队伍已满（最多4人）。"
            emit("game_msg", {"text": text, "type": "error"})
            return
        if old_team and old_team["id"] != result["id"]:
            leave_room(old_team["id"])
            socketio.emit("secret_realm_team_changed", {"team_id": old_team["id"]}, room=old_team["id"])
        join_room(result["id"])
        emit("game_msg", {"text": f"已加入秘境队伍 {result['id']}。", "type": "system"})
        _emit_state(user_id)
        socketio.emit("secret_realm_team_changed", {"team_id": result["id"]}, room=result["id"])

    @socketio.on("secret_realm_team_leave")
    def handle_secret_realm_team_leave():
        if "user_id" not in session:
            return
        user_id = session["user_id"]
        old_team = get_team_for_user(user_id)
        if not old_team:
            _emit_state(user_id)
            return
        leave_room(old_team["id"])
        leave_team(user_id)
        emit("game_msg", {"text": "你已离开秘境队伍。", "type": "system"})
        _emit_state(user_id)
        socketio.emit("secret_realm_team_changed", {"team_id": old_team["id"]}, room=old_team["id"])

    @socketio.on("claim_secret_realm_settlement")
    def handle_claim_secret_realm_settlement(data):
        if "user_id" not in session or not isinstance(data, dict):
            return
        week_id = data.get("week_id")
        if not isinstance(week_id, str) or week_id >= _week_id():
            emit("game_msg", {"text": "本周秘境尚未结算。", "type": "error"})
            return
        user_id = session["user_id"]
        game_state.save_cached_character(user_id)
        result = claim_secret_realm_settlement(user_id, week_id)
        if not result["ok"]:
            emit("game_msg", {"text": "该周没有可领取的秘境奖励。", "type": "error"})
            return
        emit("game_msg", {
            "text": f"领取 {week_id} 秘境结算：第 {result['rank']} 名，获得 {result['gold_reward']} 灵石。",
            "type": "shop",
        })
        game_state.refresh_cached_character(user_id)
        _emit_state(user_id)
        do_get_state(user_id)

    @socketio.on("secret_realm_challenge")
    def handle_secret_realm_challenge():
        if "user_id" not in session:
            return
        user_id = session["user_id"]
        char = game_state.get_cached_character(user_id)
        if not char:
            return
        game_state.touch_activity(session.get("username", ""))

        team = get_team_for_user(user_id)
        if not team:
            team = create_team(user_id)
            join_room(team["id"])
            socketio.emit("secret_realm_team_changed", {"team_id": team["id"]}, room=team["id"])

        week_id = _week_id()
        boss_config = get_weekly_boss(week_id)
        season = get_season_modifier(week_id)
        stats = get_full_stats(char)
        damage = max(1, round(stats["atk"] * 3 * season["boss_damage_multiplier"]))
        game_state.save_cached_character(user_id)
        result = resolve_secret_realm_boss_encounter(
            user_id,
            week_id,
            player_damage=damage,
            player_defense=stats["def"],
            boss_attack=boss_config["attack"],
            max_hp=boss_config["max_hp"],
            entry_limit=EXPLORATION_LIMIT,
        )
        if not result["ok"]:
            messages = {
                "no_entries": "本周秘境入场次数已耗尽，无法继续挑战首领。",
                "boss_defeated": f"{boss_config['name']}已经被击败，静待下周秘境重开。",
            }
            emit("game_msg", {"text": messages.get(result["reason"], "秘境挑战暂不可用。"), "type": "error"})
            _emit_state(user_id)
            return

        game_state.refresh_cached_character(user_id)
        if result["player_died"]:
            emit("game_msg", {
                "text": f"{boss_config['name']}反击造成 {result['player_damage']} 点伤害。你已陨落并被传送回青云镇，入场次数已消耗。",
                "type": "error",
            })
        elif result["reward_granted"]:
            emit("game_msg", {"text": f"{boss_config['name']}伏诛！你获得限定素材【赤焰晶】。", "type": "buff"})
        else:
            emit("game_msg", {
                "text": f"你对{boss_config['name']}造成 {result['damage']} 点伤害，承受反击 {result['player_damage']} 点伤害。",
                "type": "fight",
            })
        _emit_state(user_id)
        do_get_state(user_id)
