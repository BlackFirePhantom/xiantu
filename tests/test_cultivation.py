"""game.cultivation 单元测试"""

import json
import pytest
from datetime import datetime, timedelta
from game.cultivation import process_offline_cultivation, attempt_breakthrough
from game_data import MAX_LEVEL, BREAKTHROUGH_CHANCE


class TestProcessOfflineCultivation:
    def _make_char(self, level=1, exp=0, last_active=None, spirit_root="ling",
                   techniques="[]", accessory=None, sect_contrib=0):
        return {
            "level": level, "exp": exp, "last_active": last_active,
            "spirit_root": spirit_root, "techniques": techniques,
            "accessory": accessory, "sect_contrib": sect_contrib,
            "proficiency": "{}",
        }

    def test_no_last_active(self):
        char = self._make_char(last_active=None)
        gain, elapsed = process_offline_cultivation(char)
        assert gain == 0
        assert elapsed == 0

    def test_short_time(self):
        recent = (datetime.utcnow() - timedelta(seconds=5)).isoformat()
        char = self._make_char(last_active=recent)
        gain, elapsed = process_offline_cultivation(char)
        assert gain == 0

    def test_one_hour(self):
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        char = self._make_char(last_active=past)
        gain, elapsed = process_offline_cultivation(char)
        assert gain > 0
        assert elapsed >= 3500  # ~1 hour

    def test_max_level_no_gain(self):
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        char = self._make_char(level=MAX_LEVEL, last_active=past)
        gain, elapsed = process_offline_cultivation(char)
        assert gain == 0

    def test_clamped_to_24h(self):
        past = (datetime.utcnow() - timedelta(hours=48)).isoformat()
        char = self._make_char(last_active=past)
        gain, elapsed = process_offline_cultivation(char)
        assert elapsed <= 24 * 3600 + 1


class TestAttemptBreakthrough:
    def _make_char(self, level=5, hp=100):
        return {"level": level, "hp": hp}

    def test_success(self):
        char = self._make_char(level=5)
        result = attempt_breakthrough(char, 210, 1.0)  # 100% chance
        assert result["success"] is True
        assert result["new_level"] == 6
        assert "new_stats" in result

    def test_failure(self):
        char = self._make_char(level=5, hp=100)
        result = attempt_breakthrough(char, 210, 0.0)  # 0% chance
        assert result["success"] is False
        assert result["hp_loss"] > 0
