"""pytest 共享 fixtures"""

import pytest


@pytest.fixture
def make_char():
    """角色字典工厂，可通过 kwargs 覆盖任意默认字段。"""
    def _make_char(**kwargs):
        defaults = {
            "user_id": 1,
            "name": "测试修士",
            "level": 1,
            "exp": 0,
            "hp": 100,
            "max_hp": 100,
            "atk": 10,
            "def_stat": 5,
            "gold": 100,
            "location": "qingyun_town",
            "spirit_root": "ling",
            "techniques": "[]",
            "proficiency": "{}",
            "open_meridians": "[]",
            "weapon": None,
            "armor": None,
            "accessory": None,
            "pets": "[]",
            "active_pet": None,
            "kills": 0,
            "deaths": 0,
            "has_breakthrough_pill": 0,
            "combat_buff": 0,
            "sect_contrib": 0,
            "npc_goodwill": "{}",
            "active_quests": "[]",
            "completed_quests": "[]",
            "npc_gift_date": None,
            "last_active": None,
            "inventory": "{}",
        }
        defaults.update(kwargs)
        return defaults
    return _make_char


@pytest.fixture
def make_inv():
    """背包字典工厂，返回可变副本。"""
    def _make_inv(**kwargs):
        inv = {}
        inv.update(kwargs)
        return inv
    return _make_inv
