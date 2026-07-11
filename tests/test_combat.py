"""game.combat 单元测试 - 战斗文案"""

from game.combat import fmt_attack, fmt_monster_attack, ATTACK_VERBS, MONSTER_ATTACK_VERBS


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
