"""战斗文案 + 战斗纯逻辑单元测试"""

from game.combat import fmt_attack, fmt_monster_attack, ATTACK_VERBS, MONSTER_ATTACK_VERBS


# ═══════════════ 文案测试 ═══════════════

class TestFmtAttack:
    def test_returns_non_empty_string(self):
        result = fmt_attack("青狼")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_monster_name(self):
        result = fmt_attack("赤炎蛟龙")
        assert "赤炎蛟龙" in result

    def test_uses_attack_verbs(self):
        """多次调用应能覆盖不同文案（概率性验证）"""
        results = set()
        for _ in range(50):
            results.add(fmt_attack("妖兽"))
        # 至少能出现 2 种不同文案
        assert len(results) >= 2

    def test_format_substitution(self):
        """所有文案模板都应正确替换 {m} 占位符"""
        for template in ATTACK_VERBS:
            result = template.format(m="测试怪")
            assert "{" not in result
            assert "测试怪" in result


class TestFmtMonsterAttack:
    def test_returns_non_empty_string(self):
        result = fmt_monster_attack("青狼")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_monster_name(self):
        result = fmt_monster_attack("赤炎蛟龙")
        assert "赤炎蛟龙" in result

    def test_uses_monster_attack_verbs(self):
        results = set()
        for _ in range(50):
            results.add(fmt_monster_attack("妖兽"))
        assert len(results) >= 2

    def test_format_substitution(self):
        for template in MONSTER_ATTACK_VERBS:
            result = template.format(m="测试怪")
            assert "{" not in result
            assert "测试怪" in result


# ═══════════════ 战斗纯逻辑测试 ═══════════════

from handlers.combat import (
    _effective_atk, _effective_def, _decrement_buffs, _calc_damage,
    _execute_skill, _process_player_action, _monster_turn,
)
from game.combat_engine import create_combat_state, serialize_combat_state


def test_create_combat_state_provides_one_canonical_shape():
    state = create_combat_state(
        kind="wild",
        monster={"name": "青狼", "level": 1, "skills": []},
        monster_hp=30,
        monster_max_hp=30,
        monster_atk=8,
        monster_def=3,
        player_hp=100,
        player_max_hp=100,
        player_mp=50,
        player_max_mp=50,
        player_atk=10,
        player_def=5,
    )

    assert state["schema_version"] == 1
    assert state["kind"] == "wild"
    assert state["round"] == 1
    assert state["player_buffs"] == {}
    assert state["monster_debuffs"] == {}
    assert state["defending"] is False


def test_serialize_combat_state_exposes_the_shared_frontend_contract():
    state = create_combat_state(
        kind="secret_realm",
        monster={"name": "赤焰妖王", "level": 1, "skills": []},
        monster_hp=500,
        monster_max_hp=560,
        monster_atk=12,
        monster_def=4,
        player_hp=80,
        player_max_hp=100,
        player_mp=30,
        player_max_mp=50,
        player_atk=10,
        player_def=5,
        round_number=3,
        log=["第三回合"],
    )

    payload = serialize_combat_state(state, skills=[{"tech_id": "modao_rumen"}])

    assert payload == {
        "schema_version": 1,
        "kind": "secret_realm",
        "monster": {"name": "赤焰妖王", "level": 1, "skills": []},
        "monster_hp": 500,
        "monster_max_hp": 560,
        "player_hp": 80,
        "player_max_hp": 100,
        "player_mp": 30,
        "player_max_mp": 50,
        "skills": [{"tech_id": "modao_rumen"}],
        "round": 3,
        "log": ["第三回合"],
        "player_buffs": {},
        "monster_buffs": {},
    }


class TestEffectiveAtkDef:
    """测试 _effective_atk / _effective_def 的 buff/debuff 叠加。"""

    def test_base_player_atk(self, make_combat):
        combat = make_combat(player_atk=20)
        assert _effective_atk(combat, is_player=True) == 20

    def test_base_monster_atk(self, make_combat):
        combat = make_combat(monster_atk=15)
        assert _effective_atk(combat, is_player=False) == 15

    def test_buff_increases_atk(self, make_combat):
        combat = make_combat(
            player_atk=20,
            player_buffs={"atk": {"mult": 1.3, "rounds": 3}},
        )
        assert _effective_atk(combat, is_player=True) == int(20 * 1.3)

    def test_debuff_decreases_atk(self, make_combat):
        combat = make_combat(
            player_atk=20,
            player_debuffs={"atk": {"mult": 0.7, "rounds": 2}},
        )
        assert _effective_atk(combat, is_player=True) == int(20 * 0.7)

    def test_buff_and_debuff_stack(self, make_combat):
        combat = make_combat(
            player_atk=100,
            player_buffs={"atk": {"mult": 1.2, "rounds": 3}},
            player_debuffs={"atk": {"mult": 0.5, "rounds": 2}},
        )
        assert _effective_atk(combat, is_player=True) == int(100 * 1.2 * 0.5)

    def test_base_player_def(self, make_combat):
        combat = make_combat(player_def=10)
        assert _effective_def(combat, is_player=True) == 10

    def test_def_buff(self, make_combat):
        combat = make_combat(
            player_def=10,
            player_buffs={"def": {"mult": 1.5, "rounds": 2}},
        )
        assert _effective_def(combat, is_player=True) == int(10 * 1.5)


class TestDecrementBuffs:
    """测试 _decrement_buffs 的递减和过期删除。"""

    def test_rounds_decrement(self, make_combat):
        combat = make_combat(
            player_buffs={"atk": {"mult": 1.2, "rounds": 3}},
        )
        _decrement_buffs(combat)
        assert combat["player_buffs"]["atk"]["rounds"] == 2

    def test_expired_buff_removed(self, make_combat):
        combat = make_combat(
            player_buffs={"atk": {"mult": 1.2, "rounds": 1}},
            monster_debuffs={"def": {"mult": 0.8, "rounds": 1}},
        )
        _decrement_buffs(combat)
        assert "atk" not in combat["player_buffs"]
        assert "def" not in combat["monster_debuffs"]

    def test_multiple_buffs_mixed(self, make_combat):
        combat = make_combat(
            player_buffs={
                "atk": {"mult": 1.2, "rounds": 2},
                "def": {"mult": 1.5, "rounds": 1},
            },
            player_debuffs={"atk": {"mult": 0.8, "rounds": 3}},
        )
        _decrement_buffs(combat)
        assert "def" not in combat["player_buffs"]  # expired
        assert combat["player_buffs"]["atk"]["rounds"] == 1
        assert combat["player_debuffs"]["atk"]["rounds"] == 2

    def test_empty_buffs_no_error(self, make_combat):
        combat = make_combat()
        _decrement_buffs(combat)  # should not raise
        assert combat["player_buffs"] == {}


class TestCalcDamage:
    """测试 _calc_damage 伤害计算。"""

    def test_normal_damage(self, make_combat):
        combat = make_combat(player_atk=20, monster_def=5)
        dmg = _calc_damage(combat, is_player_attacker=True)
        # atk - def + random(-2, 3) = 15 + random(-2, 3) -> 13~18
        assert 13 <= dmg <= 18

    def test_floor_at_one(self, make_combat):
        # atk < def 时伤害应为 1（floor）
        combat = make_combat(player_atk=1, monster_def=100)
        dmg = _calc_damage(combat, is_player_attacker=True)
        assert dmg == 1

    def test_buff_amplifies_damage(self, make_combat):
        combat = make_combat(
            player_atk=20,
            player_buffs={"atk": {"mult": 2.0, "rounds": 3}},
            monster_def=5,
        )
        dmg = _calc_damage(combat, is_player_attacker=True)
        # effective_atk = 40, dmg = 40 - 5 + rand(-2,3) = 35 + rand
        assert 33 <= dmg <= 38

    def test_monster_attacker(self, make_combat):
        combat = make_combat(monster_atk=15, player_def=5)
        dmg = _calc_damage(combat, is_player_attacker=False)
        assert 8 <= dmg <= 13


class TestExecuteSkill:
    """测试 _execute_skill 的 7 种技能类型。"""

    def test_attack_skill(self, make_combat):
        combat = make_combat(player_atk=20, monster_def=3, monster_hp=100)
        skill = {"name": "魔道入门", "type": "attack", "power": 1.3}
        log = _execute_skill(combat, skill, None, [], is_player=True)
        assert len(log) >= 1
        assert combat["monster_hp"] < 100

    def test_multi_hit_skill(self, make_combat):
        combat = make_combat(player_atk=20, monster_def=3, monster_hp=200)
        skill = {"name": "天魔功", "type": "multi_hit", "power": 0.8, "hits": 3}
        log = _execute_skill(combat, skill, None, [], is_player=True)
        assert combat["monster_hp"] < 200
        # 3 hit lines + intro line
        assert len(log) >= 3

    def test_heal_skill(self, make_combat):
        combat = make_combat(player_hp=30, player_max_hp=100)
        skill = {"name": "基础吐纳", "type": "heal", "power": 0.15}
        _execute_skill(combat, skill, None, [], is_player=True)
        assert combat["player_hp"] > 30
        assert combat["player_hp"] <= 100

    def test_defense_skill(self, make_combat):
        combat = make_combat()
        skill = {"name": "混铁功", "type": "defense", "power": 0.4, "duration": 2}
        _execute_skill(combat, skill, None, [], is_player=True)
        assert "def" in combat["player_buffs"]
        assert combat["player_buffs"]["def"]["mult"] == 0.6
        assert combat["player_buffs"]["def"]["rounds"] == 2

    def test_buff_skill(self, make_combat):
        combat = make_combat()
        skill = {"name": "灵犀诀", "type": "buff", "power": 0.2, "target": "atk", "duration": 3}
        _execute_skill(combat, skill, None, [], is_player=True)
        assert "atk" in combat["player_buffs"]
        assert combat["player_buffs"]["atk"]["mult"] == 1.2

    def test_debuff_skill(self, make_combat):
        combat = make_combat()
        skill = {"name": "寒冰诀", "type": "debuff", "power": 0.3, "target": "monster_atk", "duration": 2}
        _execute_skill(combat, skill, None, [], is_player=True)
        assert "atk" in combat["monster_debuffs"]
        assert combat["monster_debuffs"]["atk"]["mult"] == 0.7

    def test_lifesteal_skill(self, make_combat):
        combat = make_combat(player_hp=30, player_max_hp=100, player_atk=20, monster_def=3, monster_hp=100)
        skill = {"name": "杀鬼诀", "type": "lifesteal", "power": 1.2, "lifesteal_pct": 0.3}
        _execute_skill(combat, skill, None, [], is_player=True)
        assert combat["monster_hp"] < 100
        assert combat["player_hp"] > 30  # healed by lifesteal


class TestProcessPlayerAction:
    """测试 _process_player_action 的各分支。"""

    def test_defend_heals_and_sets_flag(self, make_combat, make_char):
        combat = make_combat(player_hp=50, player_max_hp=100)
        char = make_char()
        log = _process_player_action(combat, "defend", None, char, 1)
        assert combat["defending"] is True
        assert combat["player_hp"] > 50
        assert len(log) >= 1

    def test_flee_success(self, make_combat, make_char):
        combat = make_combat(char_level=10)
        combat["monster"]["level"] = 1  # high level advantage
        char = make_char()
        # Try multiple times to hit success
        fled = False
        for _ in range(20):
            combat["_fled"] = False if "_fled" in combat else None
            combat.pop("_fled", None)
            _process_player_action(combat, "flee", None, char, 1)
            if combat.get("_fled"):
                fled = True
                break
        assert fled, "flee should eventually succeed with level advantage"

    def test_attack_deals_damage(self, make_combat, make_char):
        combat = make_combat(monster_hp=100, player_atk=20, monster_def=3)
        char = make_char()
        log = _process_player_action(combat, "attack", None, char, 1)
        assert combat["monster_hp"] < 100
        assert len(log) >= 1

    def test_attack_can_kill(self, make_combat, make_char):
        combat = make_combat(monster_hp=5, player_atk=50, monster_def=0)
        char = make_char()
        log = _process_player_action(combat, "attack", None, char, 1)
        assert combat["monster_hp"] <= 0
        assert any("倒地" in line or "碎裂" in line for line in log)

    def test_skill_no_mp_falls_back_to_attack(self, make_combat, make_char):
        combat = make_combat(player_mp=0, monster_hp=100, player_atk=20, monster_def=3)
        char = make_char(techniques='["modao_rumen"]')
        log = _process_player_action(combat, "skill", "modao_rumen", char, 1)
        assert combat["monster_hp"] < 100  # still attacked
        assert any("灵力不足" in line for line in log)


class TestMonsterTurn:
    """测试 _monster_turn 的各分支。"""

    def test_normal_attack(self, make_combat):
        combat = make_combat(
            monster_atk=10, player_def=3, player_hp=100,
            monster={"name": "青狼", "level": 1, "atk": 10, "def": 3, "hp": 30, "skills": []},
        )
        hp_before = combat["player_hp"]
        log = _monster_turn(combat)
        assert combat["player_hp"] <= hp_before
        assert len(log) >= 1

    def test_defend_reduces_damage(self, make_combat):
        """defending=True 时伤害减半。"""
        combat = make_combat(
            monster_atk=100, player_def=0, player_hp=200,
            monster={"name": "巨兽", "level": 5, "atk": 100, "def": 3, "hp": 50, "skills": []},
            defending=True,
        )
        _monster_turn(combat)
        # 伤害应该被减半，而不是全额
        assert combat["player_hp"] > 100

    def test_skill_branch(self, make_combat):
        """怪物有技能时应能触发。"""
        skill = {"name": "撕咬", "type": "attack", "power": 1.5, "chance": 1.0}
        combat = make_combat(
            monster_atk=10, player_def=3, player_hp=200,
            monster={"name": "凶兽", "level": 5, "atk": 10, "def": 3, "hp": 50, "skills": [skill]},
        )
        hp_before = combat["player_hp"]
        _monster_turn(combat)
        assert combat["player_hp"] < hp_before
