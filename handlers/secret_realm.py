"""Socket.IO transport adapters for the weekly secret realm."""

from functools import wraps

from flask import request, session
from flask_socketio import emit, join_room, leave_room

import game_state
from game.action_result import ActionResult
from game.secret_realm_team import create_team, get_team_for_user, join_team, leave_team
from game.utils import week_id as _week_id
from models import claim_secret_realm_settlement
from services.secret_realm import build_secret_realm_state, execute_secret_realm_challenge
from .base import do_get_state


def _serialize_secret_realm_action(handler):
    """Reject overlapping actions before they calculate from stale turn state."""
    @wraps(handler)
    def wrapped(data=None):
        user_id = session.get("user_id")
        if not user_id:
            return ActionResult.failure("not_authenticated").to_dict()
        lock = game_state.get_secret_realm_lock(user_id)
        if not lock.acquire(blocking=False):
            return ActionResult.failure("action_pending").to_dict()
        try:
            return handler(data)
        finally:
            lock.release()
    return wrapped


def _state_for(user_id):
    return build_secret_realm_state(user_id, _week_id())


def _emit_state(user_id):
    emit("secret_realm_state", _state_for(user_id))


def register_secret_realm_handlers(socketio):
    @socketio.on("get_secret_realm")
    def handle_get_secret_realm():
        user_id = session.get("user_id")
        if not user_id:
            return ActionResult.failure("not_authenticated").to_dict()
        _emit_state(user_id)
        return ActionResult.success().to_dict()

    @socketio.on("secret_realm_team_create")
    def handle_secret_realm_team_create():
        user_id = session.get("user_id")
        if not user_id:
            return ActionResult.failure("not_authenticated").to_dict()
        old_team = get_team_for_user(user_id)
        if old_team:
            leave_room(old_team["id"])
        team = create_team(user_id)
        join_room(team["id"])
        emit("game_msg", {
            "text": f"已创建秘境队伍，队伍码：{team['id']}。单人即可开启秘境。",
            "type": "system",
        })
        _emit_state(user_id)
        socketio.emit(
            "secret_realm_team_changed",
            {"team_id": team["id"]},
            room=team["id"],
            skip_sid=request.sid,
        )
        return ActionResult.success(team_id=team["id"]).to_dict()

    @socketio.on("secret_realm_team_join")
    def handle_secret_realm_team_join(data):
        user_id = session.get("user_id")
        if not user_id:
            return ActionResult.failure("not_authenticated").to_dict()
        if not isinstance(data, dict):
            return ActionResult.failure("invalid_payload").to_dict()
        old_team = get_team_for_user(user_id)
        result = join_team(user_id, data.get("team_id"))
        if result.get("ok") is False:
            text = "队伍不存在。" if result["reason"] == "team_not_found" else "队伍已满（最多4人）。"
            emit("game_msg", {"text": text, "type": "error"})
            return ActionResult.failure(result["reason"]).to_dict()
        if old_team and old_team["id"] != result["id"]:
            leave_room(old_team["id"])
            socketio.emit(
                "secret_realm_team_changed",
                {"team_id": old_team["id"]},
                room=old_team["id"],
            )
        join_room(result["id"])
        emit("game_msg", {"text": f"已加入秘境队伍 {result['id']}。", "type": "system"})
        _emit_state(user_id)
        socketio.emit(
            "secret_realm_team_changed",
            {"team_id": result["id"]},
            room=result["id"],
        )
        return ActionResult.success(team_id=result["id"]).to_dict()

    @socketio.on("secret_realm_team_leave")
    def handle_secret_realm_team_leave():
        user_id = session.get("user_id")
        if not user_id:
            return ActionResult.failure("not_authenticated").to_dict()
        old_team = get_team_for_user(user_id)
        if not old_team:
            _emit_state(user_id)
            return ActionResult.success().to_dict()
        leave_room(old_team["id"])
        leave_team(user_id)
        emit("game_msg", {"text": "你已离开秘境队伍。", "type": "system"})
        _emit_state(user_id)
        socketio.emit(
            "secret_realm_team_changed",
            {"team_id": old_team["id"]},
            room=old_team["id"],
        )
        return ActionResult.success().to_dict()

    @socketio.on("claim_secret_realm_settlement")
    def handle_claim_secret_realm_settlement(data):
        user_id = session.get("user_id")
        if not user_id:
            return ActionResult.failure("not_authenticated").to_dict()
        if not isinstance(data, dict):
            return ActionResult.failure("invalid_payload").to_dict()
        week_id = data.get("week_id")
        if not isinstance(week_id, str) or week_id >= _week_id():
            emit("game_msg", {"text": "本周秘境尚未结算。", "type": "error"})
            return ActionResult.failure("settlement_not_ready").to_dict()
        game_state.save_cached_character(user_id)
        result = claim_secret_realm_settlement(user_id, week_id)
        if not result["ok"]:
            emit("game_msg", {"text": "该周没有可领取的秘境奖励。", "type": "error"})
            return ActionResult.failure(result["reason"]).to_dict()
        emit("game_msg", {
            "text": f"领取 {week_id} 秘境结算：第 {result['rank']} 名，获得 {result['gold_reward']} 灵石。",
            "type": "shop",
        })
        game_state.refresh_cached_character(user_id)
        _emit_state(user_id)
        do_get_state(user_id)
        return ActionResult.success(week_id=week_id, rank=result["rank"]).to_dict()

    @socketio.on("secret_realm_challenge")
    @_serialize_secret_realm_action
    def handle_secret_realm_challenge(data=None):
        user_id = session["user_id"]
        character = game_state.get_cached_character(user_id)
        if not character:
            return ActionResult.failure("character_missing").to_dict()
        game_state.touch_activity(session.get("username", ""))

        team = get_team_for_user(user_id)
        if not team:
            team = create_team(user_id)
            join_room(team["id"])
            socketio.emit(
                "secret_realm_team_changed",
                {"team_id": team["id"]},
                room=team["id"],
                skip_sid=request.sid,
            )

        outcome = execute_secret_realm_challenge(
            user_id,
            _week_id(),
            data,
            team=team,
        )
        if outcome.user_message:
            emit("game_msg", outcome.user_message)
        if outcome.team_message and outcome.team_id:
            socketio.emit(
                "game_msg",
                outcome.team_message,
                room=outcome.team_id,
                skip_sid=request.sid,
            )
        if outcome.notify_team_changed and outcome.team_id:
            socketio.emit(
                "secret_realm_team_changed",
                {"team_id": outcome.team_id},
                room=outcome.team_id,
                skip_sid=request.sid,
            )
        if outcome.refresh_realm_state:
            _emit_state(user_id)
        if outcome.refresh_game_state:
            do_get_state(user_id)
        return outcome.ack.to_dict()
