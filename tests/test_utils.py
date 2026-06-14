"""game.utils 单元测试"""

import json
import pytest
from game.utils import (
    calc_level_stats, get_exp_needed, format_duration,
    proficiency_mult, get_proficiency,
)
from game_data import MAX_LEVEL


class TestCalcLevelStats:
    def test_level_1(self):
        s = calc_level_stats(1)
        assert s == {"max_hp": 100, "atk": 10, "def_stat": 5}

    def test_level_10(self):
        s = calc_level_stats(10)
        assert s["max_hp"] == 100 + 9 * 15
        assert s["atk"] == 10 + 9 * 3
        assert s["def_stat"] == 5 + 9 * 2


class TestGetExpNeeded:
    def test_max_level(self):
        assert get_exp_needed(MAX_LEVEL) == "-"

    def test_level_2(self):
        assert get_exp_needed(2) == 50

    def test_level_1(self):
        assert get_exp_needed(1) == 0


class TestFormatDuration:
    def test_seconds(self):
        assert format_duration(30) == "30秒"

    def test_minutes(self):
        assert format_duration(120) == "2分钟"

    def test_hours(self):
        assert format_duration(3720) == "1小时2分钟"

    def test_exact_hour(self):
        assert format_duration(3600) == "1小时"


class TestProficiencyMult:
    def test_zero(self):
        assert proficiency_mult(0) == 0.5

    def test_max(self):
        from game_data import TECHNIQUE_MAX_PROFICIENCY
        assert proficiency_mult(TECHNIQUE_MAX_PROFICIENCY) == 1.0

    def test_half(self):
        from game_data import TECHNIQUE_MAX_PROFICIENCY
        assert proficiency_mult(TECHNIQUE_MAX_PROFICIENCY // 2) == pytest.approx(0.75)


class TestGetProficiency:
    def test_empty(self):
        char = {"proficiency": None}
        assert get_proficiency(char) == {}

    def test_with_data(self):
        char = {"proficiency": json.dumps({"jichu_tuna": 100})}
        prof = get_proficiency(char)
        assert prof["jichu_tuna"] == 100
