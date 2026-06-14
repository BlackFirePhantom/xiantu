"""game.npc 单元测试"""

import json
import pytest
from game.npc import (
    get_npc_info_for_location, get_quest_info, get_sect_info,
    accept_quest, complete_quest, check_quest_progress,
)


def _make_char(**kwargs):
    defaults = {
        "user_id": 1, "name": "测试", "level": 1, "exp": 0,
        "hp": 100, "gold": 50, "location": "qingyun_town",
        "spirit_root": "ling", "techniques": "[]",
        "npc_goodwill": "{}", "active_quests": "[]",
        "completed_quests": "[]", "sect_contrib": 0,
        "npc_gift_date": "{}",
    }
    defaults.update(kwargs)
    return defaults


class TestGetNpcInfo:
    def test_qingyun_town_npcs(self):
        char = _make_char()
        npcs = get_npc_info_for_location(char)
        assert len(npcs) >= 1
        names = [n["name"] for n in npcs]
        assert "苏万金" in names

    def test_other_location(self):
        char = _make_char(location="tribulation_peak")
        npcs = get_npc_info_for_location(char)
        assert len(npcs) == 0


class TestGetSectInfo:
    def test_outer_disciple(self):
        char = _make_char(sect_contrib=0)
        info = get_sect_info(char)
        assert info["rank_name"] == "外门弟子"

    def test_inner_disciple(self):
        char = _make_char(sect_contrib=50)
        info = get_sect_info(char)
        assert info["rank_name"] == "内门弟子"


class TestAcceptQuest:
    def test_valid(self):
        char = _make_char()
        result = accept_quest(char, "dq_wolf_hunt")
        assert result["success"] is True
        assert len(result["updated_active_quests"]) == 1

    def test_already_accepted(self):
        char = _make_char(active_quests=json.dumps([{"id": "dq_wolf_hunt", "progress": {}}]))
        result = accept_quest(char, "dq_wolf_hunt")
        assert result["success"] is False

    def test_level_too_low(self):
        char = _make_char(level=1)
        result = accept_quest(char, "qt_sect_inner")
        assert result["success"] is False


class TestCheckQuestProgress:
    def test_kill_progress(self):
        char = _make_char(active_quests=json.dumps([
            {"id": "dq_wolf_hunt", "progress": {}}
        ]))
        changed, updated = check_quest_progress(char, "kill", "green_wolf")
        assert changed is True
        assert updated[0]["progress"]["kill_green_wolf"] == 1

    def test_no_match(self):
        char = _make_char(active_quests=json.dumps([
            {"id": "dq_wolf_hunt", "progress": {}}
        ]))
        changed, updated = check_quest_progress(char, "kill", "spirit_slime")
        assert changed is False
