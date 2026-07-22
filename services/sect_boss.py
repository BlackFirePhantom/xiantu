"""Application service for the weekly shared sect boss."""

from dataclasses import dataclass

import game_state
from game.action_result import ActionResult
from game.utils import get_full_stats
from models import apply_sect_boss_damage, get_sect_boss, get_sect_boss_leaderboard


SECT_BOSS_MAX_HP = 1200


@dataclass(frozen=True, slots=True)
class SectBossChallengeOutcome:
    ack: ActionResult
    message: dict
    refresh_game_state: bool = False


def build_sect_boss_state(week_id):
    """Build the shared boss projection without Flask or Socket.IO."""
    return {
        "schema_version": 1,
        "kind": "sect_boss",
        "week_id": week_id,
        "name": "护宗魔蛟",
        "boss": get_sect_boss(week_id, max_hp=SECT_BOSS_MAX_HP),
        "leaderboard": get_sect_boss_leaderboard(week_id),
    }


def execute_sect_boss_challenge(user_id, week_id, character):
    """Resolve one sect-boss strike and return a transport-neutral outcome."""
    if not character:
        return SectBossChallengeOutcome(
            ActionResult.failure("character_missing"),
            {"text": "角色不存在。", "type": "error"},
        )

    damage = max(1, get_full_stats(character)["atk"] * 2)
    game_state.save_cached_character(user_id)
    result = apply_sect_boss_damage(
        user_id,
        week_id,
        damage,
        max_hp=SECT_BOSS_MAX_HP,
    )
    if not result["ok"]:
        return SectBossChallengeOutcome(
            ActionResult.failure(result["reason"]),
            {"text": "护宗魔蛟已被镇压，静候下周再战。", "type": "error"},
        )

    game_state.refresh_cached_character(user_id)
    if result["reward_granted"]:
        message = {
            "text": "护宗魔蛟伏诛！你获得了限量材料【宗门令牌】。",
            "type": "buff",
        }
    else:
        message = {
            "text": f"你对护宗魔蛟造成 {result['damage']} 点伤害。",
            "type": "fight",
        }
    return SectBossChallengeOutcome(
        ActionResult.success(
            damage=result["damage"],
            boss_hp=result["boss_hp"],
            defeated=result["defeated"],
        ),
        message,
        refresh_game_state=True,
    )
