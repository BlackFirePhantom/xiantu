"""game.pet 单元测试"""

import json
import pytest
from game.pet import get_pet_display_info, hatch_pet_egg, feed_pet
from game_data import PET_SPECIES


class TestGetPetDisplayInfo:
    def test_no_pets(self):
        char = {"pets": "[]", "active_pet": None}
        result = get_pet_display_info(char)
        assert result == []

    def test_one_pet(self):
        char = {
            "pets": json.dumps([{"id": "abc", "species_id": "spirit_fox", "level": 3, "exp": 20}]),
            "active_pet": "abc",
        }
        result = get_pet_display_info(char)
        assert len(result) == 1
        assert result[0]["name"] == "灵狐"
        assert result[0]["is_active"] is True
        assert result[0]["level"] == 3


class TestHatchPetEgg:
    def test_no_egg(self):
        char = {"pets": "[]"}
        inv = {}
        result = hatch_pet_egg(char, inv, "egg_common")
        assert result["success"] is False

    def test_hatch(self):
        char = {"pets": "[]"}
        inv = {"egg_common": 1}
        result = hatch_pet_egg(char, inv, "egg_common")
        assert result["success"] is True
        assert len(result["updated_pets"]) == 1
        assert "egg_common" not in result["updated_inv"]
        assert "灵兽" in result["message"] or "破壳" in result["message"]


class TestFeedPet:
    def test_no_food(self):
        char = {"pets": json.dumps([{"id": "p1", "species_id": "spirit_fox", "level": 1, "exp": 0}])}
        inv = {}
        result = feed_pet(char, inv, "p1", "pet_feed")
        assert result["success"] is False

    def test_feed(self):
        char = {"pets": json.dumps([{"id": "p1", "species_id": "spirit_fox", "level": 1, "exp": 0}])}
        inv = {"pet_feed": 1}
        result = feed_pet(char, inv, "p1", "pet_feed")
        assert result["success"] is True
        assert "pet_feed" not in result["updated_inv"]
