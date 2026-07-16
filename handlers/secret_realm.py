"""Socket.IO handlers for the weekly secret realm."""

from datetime import date
import random

from flask import session
from flask_socketio import emit

import game_state
from game.secret_realm import BOSS_MAX_HP, challenge_boss, explore
from game.utils import get_full_stats
from models import (
    get_character,
    get_character_inventory,
    get_secret_realm_boss,
    get_secret_realm_leaderboard,
    get_secret_realm_run,
    save_secret_realm_boss,
    save_secret_realm_run,
    set_character_inventory,
    update_character,
)
from .base import do_get_state


def _week_id(today=None):
    iso_week = (today or date.today()).isocalendar()
    return f"{iso_week.year}-W{iso_week.week:02d}"


def _state_for(user_id):
    week_id = _week_id()
    run = get_secret_realm_run(user_id, week_id)
    boss = get_secret_realm_boss(week_id, max_hp=BOSS_MAX_HP)
    return {
        "week_id": week_id,
        "name": "赤焰秘境",
        "explorations": run["explorations"],
        "exploration_limit": 3,
        "contribution": run["contribution"],
        "boss_damage": run["boss_damage"],
        "boss": boss,
        "leaderboard": get_secret_realm_leaderboard(week_id),
    }


def _emit_state(user_id):
    emit("secret_realm_state", _state_for(user_id))


def register_secret_realm_handlers(socketio):
    @socketio.on("get_secret_realm")
    def handle_get_secret_realm():
        if "user_id" in session:
            _emit_state(session["user_id"])

    @socketio.on("secret_realm_explore")
    def handle_secret_realm_explore():
        if "user_id" not in session:
            return
        user_id = session["user_id"]
        char = get_character(user_id)
        if not char:
            return
        game_state.touch_activity(session.get("username", ""))

        week_id = _week_id()
        result = explore(get_secret_realm_run(user_id, week_id), random.randint(0, 7))
        if not result["ok"]:
            emit("game_msg", {"text": "本周秘境探索次数已耗尽。", "type": "error"})
            return

        run = result["run"]
        save_secret_realm_run(user_id, week_id, **run)
        update_character(
            user_id,
            gold=char["gold"] + result["gold_gain"],
            sect_contrib=char["sect_contrib"] + result["contribution_gain"],
        )
        suffix = "秘境深处的赤焰魔君已现身！" if result["boss_unlocked"] else ""
        emit("game_msg", {
            "text": f"秘境探索成功，获得 {result['gold_gain']} 灵石与 {result['contribution_gain']} 秘境贡献。{suffix}",
            "type": "shop",
        })
        _emit_state(user_id)
        do_get_state(user_id)

    @socketio.on("secret_realm_challenge")
    def handle_secret_realm_challenge():
        if "user_id" not in session:
            return
        user_id = session["user_id"]
        char = get_character(user_id)
        if not char:
            return
        game_state.touch_activity(session.get("username", ""))

        week_id = _week_id()
        boss = get_secret_realm_boss(week_id, max_hp=BOSS_MAX_HP)
        damage = max(1, get_full_stats(char)["atk"] * 3)
        result = challenge_boss(get_secret_realm_run(user_id, week_id), boss["hp"], damage)
        if not result["ok"]:
            messages = {
                "boss_locked": "完成三次秘境探索后，才能挑战首领。",
                "boss_defeated": "赤焰魔君已经被击败，静待下周秘境重开。",
            }
            emit("game_msg", {"text": messages[result["reason"]], "type": "error"})
            return

        run = result["run"]
        save_secret_realm_run(user_id, week_id, **run)
        save_secret_realm_boss(week_id, hp=result["boss_hp"])
        update_character(user_id, sect_contrib=char["sect_contrib"] + result["damage"])
        if result["defeated"]:
            inventory = get_character_inventory(user_id)
            inventory["chiyan_jing"] = inventory.get("chiyan_jing", 0) + 1
            set_character_inventory(user_id, inventory)
            emit("game_msg", {"text": "赤焰魔君伏诛！你获得限定素材【赤炎晶】。", "type": "buff"})
        else:
            emit("game_msg", {"text": f"你对赤焰魔君造成 {result['damage']} 点伤害。", "type": "fight"})
        _emit_state(user_id)
        do_get_state(user_id)
