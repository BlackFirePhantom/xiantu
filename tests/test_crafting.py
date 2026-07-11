"""game.crafting 单元测试 - 炼丹与锻造"""

import pytest
from unittest.mock import patch
from game.crafting import try_refine_pill, try_forge, get_forge_recipes_list
from game_data import RECIPES, FORGE_RECIPES, ITEMS


# ═══════════════ 炼丹 ═══════════════

class TestTryRefinePill:
    def test_recipe_not_exist(self, make_char, make_inv):
        char = make_char(level=5)
        inv = make_inv(lingcao=10)
        result = try_refine_pill("nonexistent", char, inv)
        assert result["success"] is False
        assert "配方不存在" in result["message"]
        assert result["updated_inv"] == inv

    def test_realm_too_low(self, make_char, make_inv):
        char = make_char(level=1)
        inv = make_inv(lingcao=10)
        # 找一个 req_realm > 1 的配方
        high_recipe_id = None
        for rid, r in RECIPES.items():
            if r["req_realm"] > 1:
                high_recipe_id = rid
                break
        if not high_recipe_id:
            pytest.skip("没有 req_realm > 1 的配方")
        result = try_refine_pill(high_recipe_id, char, inv)
        assert result["success"] is False
        assert "境界不足" in result["message"]

    def test_materials_insufficient(self, make_char, make_inv):
        char = make_char(level=5)
        inv = make_inv()  # 空背包
        # 用第一个配方测试
        rid = list(RECIPES.keys())[0]
        result = try_refine_pill(rid, char, inv)
        assert result["success"] is False
        assert "材料不足" in result["message"]

    def test_success(self, make_char, make_inv):
        char = make_char(level=5)
        # 用 huiqi_dan 配方：需要 lingcao x3
        inv = make_inv(lingcao=10)
        result = try_refine_pill("huiqi_dan", char, inv)
        assert result["success"] is True
        assert "丹成" in result["message"]
        # 材料被扣除
        assert inv["lingcao"] == 7
        # 产出被添加
        assert inv["huiqi_dan"] == 1

    def test_consumes_last_material(self, make_char, make_inv):
        """材料恰好够时，扣完后从背包移除"""
        char = make_char(level=5)
        inv = make_inv(lingcao=3)  # 恰好够 huiqi_dan
        result = try_refine_pill("huiqi_dan", char, inv)
        assert result["success"] is True
        assert "lingcao" not in inv
        assert inv["huiqi_dan"] == 1


# ═══════════════ 锻造 ═══════════════

class TestTryForge:
    def test_recipe_not_exist(self, make_char, make_inv):
        char = make_char(level=5)
        inv = make_inv(hantie_kuang=10, yaogu=10)
        result = try_forge("nonexistent", char, inv)
        assert result["success"] is False
        assert result["item_id"] is None

    def test_realm_too_low(self, make_char, make_inv):
        char = make_char(level=1)
        # 找一个 req_realm > 1 的锻造配方
        high_recipe_id = None
        for rid, r in FORGE_RECIPES.items():
            if r["req_realm"] > 1:
                high_recipe_id = rid
                break
        if not high_recipe_id:
            pytest.skip("没有 req_realm > 1 的锻造配方")
        inv = make_inv(hantie_kuang=10, yaogu=10)
        result = try_forge(high_recipe_id, char, inv)
        assert result["success"] is False
        assert "境界不足" in result["log"][0]

    def test_materials_insufficient(self, make_char, make_inv):
        char = make_char(level=5)
        inv = make_inv()  # 空背包
        result = try_forge("forge_t1_weapon", char, inv)
        assert result["success"] is False
        assert "材料不足" in result["log"][0]

    def test_success(self, make_char, make_inv):
        char = make_char(level=5)
        inv = make_inv(hantie_kuang=5, yaogu=5)
        with patch("game.crafting.random.random", return_value=0.0):  # 0.0 < success_rate -> 成功
            result = try_forge("forge_t1_weapon", char, inv)
        assert result["success"] is True
        assert result["item_id"] is not None
        assert result["item_data"] is not None
        # 材料被扣除
        assert inv["hantie_kuang"] == 3
        assert inv["yaogu"] == 4
        # 装备被添加
        assert result["item_id"] in inv

    def test_failure(self, make_char, make_inv):
        char = make_char(level=5)
        inv = make_inv(hantie_kuang=5, yaogu=5)
        with patch("game.crafting.random.random", return_value=0.999):  # 0.999 >= 0.99 cap -> 失败
            result = try_forge("forge_t1_weapon", char, inv)
        assert result["success"] is False
        assert result["item_id"] is None
        # 材料仍被扣除（锻造失败材料消失）
        assert inv["hantie_kuang"] == 3
        assert inv["yaogu"] == 4

    def test_realm_bonus_increases_rate(self, make_char, make_inv):
        """高境界角色锻造低级配方时，成功率应有境界加成"""
        char_low = make_char(level=1)
        char_high = make_char(level=10)
        inv = make_inv()
        recipes_low = get_forge_recipes_list(char_low, inv)
        recipes_high = get_forge_recipes_list(char_high, inv)
        # 找到同一个配方的成功率对比
        for rl, rh in zip(recipes_low, recipes_high):
            if rl["id"] == rh["id"] and rl["id"] == "forge_t1_weapon":
                assert rh["success_rate"] >= rl["success_rate"]
                break


# ═══════════════ 锻造配方列表 ═══════════════

class TestGetForgeRecipesList:
    def test_returns_all_recipes(self, make_char, make_inv):
        char = make_char(level=5)
        inv = make_inv()
        recipes = get_forge_recipes_list(char, inv)
        assert len(recipes) == len(FORGE_RECIPES)

    def test_recipe_fields(self, make_char, make_inv):
        char = make_char(level=5)
        inv = make_inv()
        recipes = get_forge_recipes_list(char, inv)
        r = recipes[0]
        assert "id" in r
        assert "name" in r
        assert "slot" in r
        assert "slot_name" in r
        assert "tier" in r
        assert "success_rate" in r
        assert "req_realm" in r
        assert "can_craft" in r
        assert "ingredients" in r

    def test_can_craft_false_when_materials_missing(self, make_char, make_inv):
        char = make_char(level=5)
        inv = make_inv()  # 空背包
        recipes = get_forge_recipes_list(char, inv)
        # 没有材料时所有配方都不可制作
        for r in recipes:
            assert r["can_craft"] is False

    def test_can_craft_true_with_materials(self, make_char, make_inv):
        char = make_char(level=5)
        # forge_t1_weapon 需要 hantie_kuang x2 + yaogu x1
        inv = make_inv(hantie_kuang=5, yaogu=5)
        recipes = get_forge_recipes_list(char, inv)
        weapon_recipe = next(r for r in recipes if r["id"] == "forge_t1_weapon")
        assert weapon_recipe["can_craft"] is True

    def test_can_craft_false_when_realm_too_low(self, make_char, make_inv):
        char = make_char(level=1)
        inv = make_inv(hantie_kuang=99, yaogu=99)
        recipes = get_forge_recipes_list(char, inv)
        # 找到 req_realm > 1 的配方
        for r in recipes:
            # 检查是否有不可制作的（因境界不足）
            original = FORGE_RECIPES[r["id"]]
            if original["req_realm"] > 1:
                assert r["can_craft"] is False
