"""Application service for the weekly secret realm."""

from dataclasses import dataclass
import logging
import random

import game_state
from game.action_result import ActionResult
from game.combat_engine import (
    create_combat_state,
    decrement_buffs,
    effective_atk,
    effective_def,
    get_player_skills,
    process_player_action,
)
from game.secret_realm import EXPLORATION_LIMIT, get_season_modifier, get_weekly_boss
from game.secret_realm_team import get_team_for_user
from game.utils import get_full_stats
from game_data import SPIRIT_ROOTS, TECHNIQUES
from models import (
    get_character,
    get_character_titles,
    get_pending_secret_realm_settlements,
    get_secret_realm_boss,
    get_secret_realm_combat_state,
    get_secret_realm_leaderboard,
    get_secret_realm_run,
    resolve_secret_realm_boss_encounter,
)


logger = logging.getLogger("xiantu.secret_realm.service")


@dataclass(frozen=True, slots=True)
class SecretRealmChallengeOutcome:
    ack: ActionResult
    user_message: dict | None = None
    team_message: dict | None = None
    team_id: str | None = None
    refresh_realm_state: bool = False
    refresh_game_state: bool = False
    notify_team_changed: bool = False


def build_secret_realm_team_state(user_id):
    team = get_team_for_user(user_id)
    if not team:
        return None
    members = []
    for member_id in team["members"]:
        character = game_state.get_cached_character(member_id) or get_character(member_id)
        members.append({
            "id": member_id,
            "name": character["name"] if character else f"玩家{member_id}",
        })
    return {
        "id": team["id"],
        "leader_id": team["leader_id"],
        "is_leader": team["leader_id"] == user_id,
        "members": members,
        "max_members": 4,
    }


def build_secret_realm_state(user_id, week_id):
    """Build the complete read projection without depending on Flask or Socket.IO."""
    run = get_secret_realm_run(user_id, week_id)
    boss_config = get_weekly_boss(week_id)
    boss = get_secret_realm_boss(week_id, max_hp=boss_config["max_hp"])
    boss.update(boss_config)
    character = game_state.get_cached_character(user_id)
    combat_state = get_secret_realm_combat_state(user_id, week_id) or {"round": 1}
    stats = get_full_stats(character) if character else {"max_hp": 0, "max_mp": 0}
    player_mp = (
        int(character["mp"])
        if character and character.get("mp") is not None
        else stats.get("max_mp", 0)
    )
    return {
        "week_id": week_id,
        "name": "轮回秘境",
        "entries_remaining": max(0, EXPLORATION_LIMIT - run["explorations"]),
        "contribution": run["contribution"],
        "boss_damage": run["boss_damage"],
        "boss": boss,
        "player": {
            "hp": character["hp"],
            "max_hp": stats["max_hp"],
            "mp": player_mp,
            "max_mp": stats.get("max_mp", player_mp),
        } if character else None,
        "combat": combat_state,
        "skills": get_player_skills(character) if character else [],
        "leaderboard": get_secret_realm_leaderboard(week_id),
        "pending_settlements": get_pending_secret_realm_settlements(user_id, week_id),
        "season": get_season_modifier(week_id),
        "titles": get_character_titles(user_id),
        "team": build_secret_realm_team_state(user_id),
    }


def _valid_action_id(data):
    action_id = data.get("action_id") if isinstance(data, dict) else None
    if action_id is None:
        return None
    if not isinstance(action_id, str) or not 8 <= len(action_id) <= 96:
        return False
    return action_id


def _realm_turn_state(combat):
    return {
        "round": int(combat.get("round", 1)),
        "player_buffs": combat.get("player_buffs", {}),
        "player_debuffs": combat.get("player_debuffs", {}),
        "monster_buffs": combat.get("monster_buffs", {}),
        "monster_debuffs": combat.get("monster_debuffs", {}),
        "monster_defending": bool(combat.get("monster_defending", False)),
    }


def _restore_realm_turn_state(combat, state):
    if not isinstance(state, dict):
        return
    combat["round"] = max(1, int(state.get("round", 1)))
    for key in ("player_buffs", "player_debuffs", "monster_buffs", "monster_debuffs"):
        value = state.get(key)
        combat[key] = value if isinstance(value, dict) else {}
    combat["monster_defending"] = bool(state.get("monster_defending", False))


def _team_modifiers(team):
    team_size = len(team.get("members", [])) if team else 1
    attack_multiplier = 1.0
    defense_multiplier = 1.0
    resonance_damage_multiplier = 1.0
    negate_counter_chance = 0.0
    prefix_log = []

    if team:
        distinct_elements = set()
        huntian_count = 0
        for member_id in team.get("members", []):
            character = game_state.get_cached_character(member_id) or get_character(member_id)
            if not character:
                continue
            spirit_root = character.get("spirit_root")
            element = SPIRIT_ROOTS.get(spirit_root, {}).get("element") if spirit_root else None
            if element:
                distinct_elements.add(element)
            elif spirit_root == "huntian":
                huntian_count += 1

        if team_size == 2:
            attack_multiplier, defense_multiplier = 1.05, 1.10
        elif team_size == 3:
            attack_multiplier, defense_multiplier = 1.10, 1.15
        elif team_size >= 4:
            attack_multiplier, defense_multiplier = 1.15, 1.20

        element_count = min(5, len(distinct_elements) + huntian_count * 2)
        resonance_name = ""
        if element_count == 3:
            resonance_name, resonance_damage_multiplier = "三才聚灵", 1.15
        elif element_count == 4:
            resonance_name, resonance_damage_multiplier = "四象乾坤", 1.25
        elif element_count >= 5:
            resonance_name, resonance_damage_multiplier = "五行大阵", 1.35
            negate_counter_chance = 0.20

        if team_size > 1:
            prefix_log.append(
                f"【队伍协作】队伍共 {team_size} 人，攻击提升 "
                f"{int((attack_multiplier - 1) * 100)}%，防御提升 "
                f"{int((defense_multiplier - 1) * 100)}%。"
            )
        if resonance_name:
            description = (
                f"【五行共鸣】触发【{resonance_name}】，伤害额外提升 "
                f"{int((resonance_damage_multiplier - 1) * 100)}%！"
            )
            if negate_counter_chance:
                description += f"（有 {int(negate_counter_chance * 100)}% 概率免受反击）"
            prefix_log.append(description)

    return {
        "team_size": team_size,
        "attack_multiplier": attack_multiplier,
        "defense_multiplier": defense_multiplier,
        "resonance_damage_multiplier": resonance_damage_multiplier,
        "negate_counter_chance": negate_counter_chance,
        "prefix_log": prefix_log,
    }


def execute_secret_realm_challenge(user_id, week_id, data=None, team=None):
    """Execute one realm turn and return transport-agnostic messages and acknowledgement."""
    character = game_state.get_cached_character(user_id)
    if not character:
        return SecretRealmChallengeOutcome(ActionResult.failure("character_missing"))

    action = data.get("action", "attack") if isinstance(data, dict) else "attack"
    if not isinstance(action, str):
        action = "attack"
    skill_id = data.get("skill_id") if isinstance(data, dict) else None
    action_id = _valid_action_id(data)
    if action_id is False:
        return SecretRealmChallengeOutcome(
            ActionResult.failure("invalid_action_id"),
            {"text": "秘境行动凭据无效，请刷新页面后重试。", "type": "error"},
        )
    if action not in {"attack", "skill", "defend"}:
        return SecretRealmChallengeOutcome(
            ActionResult.failure("invalid_action", action_id=action_id),
            {"text": "无效的秘境行动。", "type": "error"},
        )

    boss_config = get_weekly_boss(week_id)
    season = get_season_modifier(week_id)
    stats = get_full_stats(character)
    selected_skill = TECHNIQUES.get(skill_id, {}).get("skill") if action == "skill" else None
    learned_ids = {skill["tech_id"] for skill in get_player_skills(character)}
    if action == "skill" and (not selected_skill or skill_id not in learned_ids):
        return SecretRealmChallengeOutcome(
            ActionResult.failure("skill_not_learned", action_id=action_id),
            {"text": "你尚未掌握这项技能。", "type": "error"},
        )

    current_mp = int(character.get("mp", stats.get("max_mp", 0)))
    if selected_skill and current_mp < int(selected_skill.get("mp_cost", 0)):
        return SecretRealmChallengeOutcome(
            ActionResult.failure("insufficient_mp", action_id=action_id),
            {
                "text": (
                    f"灵力不足，施展【{selected_skill['name']}】需要 "
                    f"{selected_skill.get('mp_cost', 0)} 点灵力。请使用回灵丹。"
                ),
                "type": "error",
            },
            refresh_realm_state=True,
        )

    team = team or get_team_for_user(user_id)
    modifiers = _team_modifiers(team)
    boss = get_secret_realm_boss(week_id, max_hp=boss_config["max_hp"])
    combat = create_combat_state(
        kind="secret_realm",
        monster={"name": boss_config["name"], "level": 1},
        monster_hp=boss["hp"],
        monster_max_hp=boss_config["max_hp"],
        monster_atk=boss_config["attack"],
        monster_def=boss_config.get("def", 0),
        player_hp=character["hp"],
        player_max_hp=stats["max_hp"],
        player_mp=current_mp,
        player_max_mp=stats.get("max_mp", current_mp),
        player_atk=int(stats["atk"] * modifiers["attack_multiplier"]),
        player_def=int(stats["def"] * modifiers["defense_multiplier"]),
        char_level=character.get("level", 1),
    )
    _restore_realm_turn_state(combat, get_secret_realm_combat_state(user_id, week_id))
    action_log = modifiers["prefix_log"] + process_player_action(
        combat, action, skill_id, character, user_id
    )

    damage = max(0, int(boss["hp"] - max(0, combat["monster_hp"])))
    damage = round(
        damage
        * season["boss_damage_multiplier"]
        * modifiers["resonance_damage_multiplier"]
    )
    player_defense = effective_def(combat, is_player=True)
    boss_attack = effective_atk(combat, is_player=False)
    if combat["defending"]:
        boss_attack = max(1, boss_attack // 2)
    if (
        modifiers["negate_counter_chance"] > 0
        and random.random() < modifiers["negate_counter_chance"]
    ):
        boss_attack = 0
        action_log.append("【五行护体】阵法神光大盛！你完全免受了首领的反击伤害！")

    if combat["monster_hp"] > 0:
        decrement_buffs(combat)
        combat["round"] += 1

    support_action = action == "defend" or (
        action == "skill"
        and selected_skill
        and selected_skill.get("type") in {"heal", "defense", "buff", "debuff"}
    )
    game_state.save_cached_character(user_id)
    try:
        result = resolve_secret_realm_boss_encounter(
            user_id,
            week_id,
            player_damage=damage,
            player_defense=player_defense,
            boss_attack=boss_attack,
            max_hp=boss_config["max_hp"],
            entry_limit=EXPLORATION_LIMIT,
            player_hp=combat["player_hp"],
            player_mp=combat["player_mp"],
            minimum_damage=0 if support_action else 1,
            action_id=action_id,
            combat_state=_realm_turn_state(combat),
        )
    except Exception:
        logger.exception("秘境出击结算失败 user_id=%s week_id=%s", user_id, week_id)
        return SecretRealmChallengeOutcome(
            ActionResult.failure("settlement_failed", action_id=action_id),
            {"text": "秘境结算失败，请稍后重试。", "type": "error"},
            refresh_realm_state=True,
        )

    if not result["ok"]:
        messages = {
            "no_entries": "本周秘境入场次数已耗尽，无法继续挑战首领。",
            "boss_defeated": f"{boss_config['name']}已经被击败，静待下周秘境重开。",
        }
        return SecretRealmChallengeOutcome(
            ActionResult.failure(result["reason"], action_id=action_id),
            {"text": messages.get(result["reason"], "秘境挑战暂不可用。"), "type": "error"},
            refresh_realm_state=True,
        )

    game_state.refresh_cached_character(user_id)
    team_size = modifiers["team_size"]
    team_id = team["id"] if team and team_size > 1 else None
    if result.get("duplicate"):
        return SecretRealmChallengeOutcome(
            ActionResult.success(action_id=action_id, duplicate=True),
            team_id=team_id,
            refresh_realm_state=True,
            refresh_game_state=True,
        )

    if result["player_died"]:
        user_message = {
            "text": (
                f"{boss_config['name']}反击造成 {result['player_damage']} 点伤害。"
                "你已陨落并被传送回青云镇，入场次数已消耗。"
            ),
            "type": "error",
        }
        team_message = {
            "text": (
                f"【秘境战报】队友【{character['name']}】挑战{boss_config['name']}，"
                "不幸陨落并传送回青云镇！"
            ),
            "type": "error",
        } if team_id else None
    elif result["reward_granted"]:
        user_message = {
            "text": f"{boss_config['name']}伏诛！你获得限定素材【赤焰晶】。",
            "type": "buff",
        }
        team_message = {
            "text": f"【秘境捷报】首领{boss_config['name']}已被【{character['name']}】成功击败！",
            "type": "buff",
        } if team_id else None
    else:
        user_message = {
            "text": (
                f"{' '.join(action_log)} 你对{boss_config['name']}造成 {result['damage']} 点伤害，"
                f"承受反击 {result['player_damage']} 点伤害。"
            ),
            "type": "fight",
        }
        team_message = {
            "text": (
                f"【秘境共战】队友【{character['name']}】对{boss_config['name']}出手，"
                f"造成了 {result['damage']} 点伤害，自身承受 "
                f"{result['player_damage']} 点反击伤害！"
            ),
            "type": "fight",
        } if team_id else None

    return SecretRealmChallengeOutcome(
        ActionResult.success(action_id=action_id, duplicate=False),
        user_message=user_message,
        team_message=team_message,
        team_id=team_id,
        refresh_realm_state=True,
        refresh_game_state=True,
        notify_team_changed=bool(team_id),
    )
