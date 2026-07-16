"""Socket.IO handlers for the weekly shared sect boss."""

from datetime import date

from flask import session
from flask_socketio import emit

import game_state
from game.utils import get_full_stats
from models import apply_sect_boss_damage, get_sect_boss, get_sect_boss_leaderboard
from .base import do_get_state

SECT_BOSS_MAX_HP = 1200


def _week_id(today=None):
    iso_week = (today or date.today()).isocalendar()
    return f"{iso_week.year}-W{iso_week.week:02d}"


def _state_for(user_id):
    week_id = _week_id()
    return {
        "week_id": week_id,
        "name": "护宗魔蛟",
        "boss": get_sect_boss(week_id, max_hp=SECT_BOSS_MAX_HP),
        "leaderboard": get_sect_boss_leaderboard(week_id),
    }


def _emit_state(user_id):
    emit("sect_boss_state", _state_for(user_id))


def register_sect_boss_handlers(socketio):
    @socketio.on("get_sect_boss")
    def handle_get_sect_boss():
        if "user_id" in session:
            _emit_state(session["user_id"])

    @socketio.on("sect_boss_challenge")
    def handle_sect_boss_challenge():
        if "user_id" not in session:
            return
        user_id = session["user_id"]
        char = game_state.get_cached_character(user_id)
        if not char:
            return
        game_state.touch_activity(session.get("username", ""))

        damage = max(1, get_full_stats(char)["atk"] * 2)
        game_state.save_cached_character(user_id)
        result = apply_sect_boss_damage(user_id, _week_id(), damage, max_hp=SECT_BOSS_MAX_HP)
        if not result["ok"]:
            emit("game_msg", {"text": "护宗魔蛟已被镇压，静候下周再战。", "type": "error"})
            return

        game_state.refresh_cached_character(user_id)
        if result["reward_granted"]:
            emit("game_msg", {"text": "护宗魔蛟伏诛！你获得了限量材料【宗门令牌】。", "type": "buff"})
        else:
            emit("game_msg", {"text": f"你对护宗魔蛟造成 {result['damage']} 点伤害。", "type": "fight"})
        _emit_state(user_id)
        do_get_state(user_id)
