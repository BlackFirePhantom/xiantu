"""Socket.IO handlers for the weekly shared sect boss."""

from flask import session
from flask_socketio import emit

import game_state
from game.action_result import ActionResult
from game.utils import week_id as _week_id
from services.sect_boss import build_sect_boss_state, execute_sect_boss_challenge
from .base import do_get_state


def _state_for(user_id):
    return build_sect_boss_state(_week_id())


def _emit_state(user_id):
    emit("sect_boss_state", _state_for(user_id))


def register_sect_boss_handlers(socketio):
    @socketio.on("get_sect_boss")
    def handle_get_sect_boss():
        user_id = session.get("user_id")
        if not user_id:
            return ActionResult.failure("not_authenticated").to_dict()
        _emit_state(user_id)
        return ActionResult.success().to_dict()

    @socketio.on("sect_boss_challenge")
    def handle_sect_boss_challenge():
        user_id = session.get("user_id")
        if not user_id:
            return ActionResult.failure("not_authenticated").to_dict()
        game_state.touch_activity(session.get("username", ""))
        outcome = execute_sect_boss_challenge(
            user_id,
            _week_id(),
            game_state.get_cached_character(user_id),
        )
        emit("game_msg", outcome.message)
        _emit_state(user_id)
        if outcome.refresh_game_state:
            do_get_state(user_id)
        return outcome.ack.to_dict()
