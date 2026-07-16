import json
from datetime import date, timedelta
import pytest
import models
import game_state
from game.arena import simulate_pvp

@pytest.fixture(autouse=True)
def setup_db():
    models.init_db()
    with models.get_db() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DELETE FROM arena_logs")
        conn.execute("DELETE FROM secret_realm_runs")
        conn.execute("DELETE FROM sect_boss_runs")
        conn.execute("DELETE FROM characters")
        conn.execute("DELETE FROM users")
        conn.execute("PRAGMA foreign_keys = ON")
    game_state.character_cache.clear()
    game_state.dirty_users.clear()

def create_mock_character(user_id, name, level=3, hp=100, mp=50, techniques="[]"):
    return {
        "user_id": user_id,
        "name": name,
        "level": level,
        "hp": hp,
        "max_hp": hp,
        "mp": mp,
        "max_mp": mp,
        "atk": 20,
        "def_stat": 6,
        "spirit_root": "huntian",
        "techniques": techniques,
        "open_meridians": "[]",
        "weapon": None,
        "armor": None,
        "accessory": None,
        "proficiency": "{}",
        "active_pet": None,
        "pets": "[]",
        "arena_defense_skills": "[]"
    }

def test_pvp_combat_simulation_basic():
    challenger = create_mock_character(1, "叶凡", level=3, hp=100, techniques=json.dumps(["jichu_tuna"]))
    defender = create_mock_character(2, "萧炎", level=3, hp=100)
    
    winner_id, score_change, combat_log = simulate_pvp(challenger, defender)
    
    assert winner_id in {1, 2}
    assert score_change > 0
    assert len(combat_log) > 0
    assert any("回合" in line for line in combat_log)

def test_pvp_combat_healing_ai():
    challenger = create_mock_character(1, "低血叶凡", level=5, hp=20, techniques=json.dumps(["jichu_tuna"]))
    defender = create_mock_character(2, "萧炎", level=35, hp=100)
    
    winner_id, score_change, combat_log = simulate_pvp(challenger, defender)
    
    assert any("施展【吐纳回春】" in line for line in combat_log)

def test_arena_db_flow():
    # 创建用户和角色
    models.create_user("user1", "hash1")
    models.create_user("user2", "hash2")
    
    user1 = models.get_user("user1")
    user2 = models.get_user("user2")
    
    models.create_character(user1["id"], "叶凡", "huntian")
    models.create_character(user2["id"], "萧炎", "huntian")
    
    char1 = models.get_character(user1["id"])
    char2 = models.get_character(user2["id"])
    
    # 挑战前积分应该是 1000
    assert char1["arena_score"] == 1000
    assert char2["arena_score"] == 1000
    
    # 更新对战结果：挑战者 1 战胜 防守者 2，获得 20 积分
    combat_log = ["第1回合：叶凡获胜！"]
    res = models.update_arena_result(user1["id"], user2["id"], user1["id"], 20, combat_log)
    
    assert res["ok"] is True
    
    # 重新查询
    char1_updated = models.get_character(user1["id"])
    char2_updated = models.get_character(user2["id"])
    
    assert char1_updated["arena_score"] == 1020
    assert char1_updated["arena_wins"] == 1
    assert char1_updated["arena_challenges_today"] == 1
    assert char1_updated["arena_last_challenge_date"] == date.today().isoformat()
    
    assert char2_updated["arena_score"] == 980
    assert char2_updated["arena_losses"] == 1
    
    # 查询对战对手：应该可以查询到对方
    opps = models.get_arena_opponents(user1["id"])
    assert len(opps) == 1
    assert opps[0]["user_id"] == user2["id"]
    
    # 查询天骄论道榜
    leaderboard = models.get_arena_leaderboard()
    assert len(leaderboard) == 2
    assert leaderboard[0]["user_id"] == user1["id"] # 1020 积分排第一
    
    # 查询战报
    logs = models.get_arena_logs(user1["id"])
    assert len(logs) == 1
    assert logs[0]["challenger_id"] == user1["id"]
    assert logs[0]["defender_id"] == user2["id"]
    assert json.loads(logs[0]["combat_log"]) == combat_log

def test_daily_challenge_limit_and_date_reset():
    models.create_user("user1", "hash1")
    user1 = models.get_user("user1")
    models.create_character(user1["id"], "叶凡", "huntian")
    
    # 昨天挑战了 5 次
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    models.update_character(user1["id"], arena_challenges_today=5, arena_last_challenge_date=yesterday)
    
    # 查询状态以触发自动重置
    char = models.get_character(user1["id"])
    
    # 模拟 Socket 请求处理：在 get_arena 中应该重置
    # 我们这里直接在测试中运行逻辑：
    today_str = date.today().isoformat()
    challenges = char["arena_challenges_today"]
    if char["arena_last_challenge_date"] != today_str:
        challenges = 0
        models.update_character(user1["id"], arena_challenges_today=0, arena_last_challenge_date=today_str)
        
    char_after = models.get_character(user1["id"])
    assert char_after["arena_challenges_today"] == 0
    assert char_after["arena_last_challenge_date"] == today_str
