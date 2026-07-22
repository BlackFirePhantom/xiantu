"""game.cultivation 单元测试"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from game.cultivation import process_offline_cultivation, attempt_breakthrough, compute_idle_reward
from game_data import MAX_LEVEL, BREAKTHROUGH_CHANCE


class TestProcessOfflineCultivation:
    def _make_char(self, level=1, exp=0, last_active=None, spirit_root="ling",
                   techniques="[]", accessory=None, sect_contrib=0, location="qingyun_town"):
        return {
            "level": level, "exp": exp, "last_active": last_active,
            "spirit_root": spirit_root, "techniques": techniques,
            "accessory": accessory, "sect_contrib": sect_contrib,
            "proficiency": "{}", "location": location,
        }

    def test_no_last_active(self):
        char = self._make_char(last_active=None)
        result = process_offline_cultivation(char)
        assert result["exp"] == 0
        assert result["elapsed"] == 0

    def test_short_time(self):
        recent = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        char = self._make_char(last_active=recent)
        result = process_offline_cultivation(char)
        assert result["exp"] == 0

    def test_one_hour(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        char = self._make_char(last_active=past)
        result = process_offline_cultivation(char)
        assert result["exp"] > 0
        assert result["elapsed"] >= 3500  # ~1 hour

    def test_max_level_no_gain(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        char = self._make_char(level=MAX_LEVEL, last_active=past)
        result = process_offline_cultivation(char)
        assert result["exp"] == 0

    def test_clamped_to_24h(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        char = self._make_char(last_active=past)
        result = process_offline_cultivation(char)
        assert result["elapsed"] <= 24 * 3600 + 1

    def test_offline_grants_drops_in_unsafe_zone(self):
        """离线在非安全区应获得材料掉落（与在线 AFK 路径一致）。"""
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        char = self._make_char(last_active=past, location="luoxia_plains")
        result = process_offline_cultivation(char)
        assert result["heal_to_full"] is False
        # 2 小时在非安全区，至少有机会掉落材料（72 次尝试，每次 30%）
        assert isinstance(result["drops"], list)

    def test_offline_heals_in_safe_zone(self):
        """离线在安全区应标记回满血。"""
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        char = self._make_char(last_active=past, location="qingyun_town")
        result = process_offline_cultivation(char)
        assert result["heal_to_full"] is True
        assert result["drops"] == []

    def test_offline_max_level_still_drops(self):
        """满级角色离线仍获得掉落（只是不获得修为）。"""
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        char = self._make_char(level=MAX_LEVEL, last_active=past, location="luoxia_plains")
        result = process_offline_cultivation(char)
        assert result["exp"] == 0
        assert isinstance(result["drops"], list)


class TestComputeIdleReward:
    def _make_char(self, level=1, location="qingyun_town"):
        return {
            "level": level, "spirit_root": "ling", "techniques": "[]",
            "proficiency": "{}", "sect_contrib": 0, "accessory": None,
            "location": location,
        }

    def test_safe_zone_heals(self):
        char = self._make_char(location="qingyun_town")
        reward = compute_idle_reward(char, 3600)
        assert reward["heal_to_full"] is True
        assert reward["drops"] == []

    def test_unsafe_zone_drops(self):
        char = self._make_char(location="luoxia_plains")
        reward = compute_idle_reward(char, 3600)
        assert reward["heal_to_full"] is False

    def test_clamped_to_max_hours(self):
        char = self._make_char()
        reward = compute_idle_reward(char, 999 * 3600)
        assert reward["elapsed"] <= 24 * 3600


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
