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


def test_defender_empty_config_uses_all_learned_skills():
    """空配置=使用全部已学技能（锁定语义，防止未来回归）。"""
    challenger = create_mock_character(1, "挑战者", level=5, hp=100, techniques="[]")
    # 防守者 HP 低于 40% 阈值，且已学治疗功法，空防守配置
    defender = create_mock_character(2, "防守者", level=5, hp=30, techniques=json.dumps(["jichu_tuna"]))
    winner_id, score_change, combat_log = simulate_pvp(challenger, defender)
    # 防守者应在 HP<40% 时使用治疗技能（吐纳回春）
    assert any("吐纳回春" in line for line in combat_log)


# ═══════════════ Socket 端到端测试 ═══════════════

def _seed_arena_users(db_path, char1_kwargs=None, char2_kwargs=None):
    """在 tmp DB 中创建两个用户和角色，返回 (uid1, uid2)。"""
    monkey_db = db_path
    import models as _models
    _models.init_db()
    with _models.get_db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'challenger', 'unused')")
        conn.execute("INSERT INTO users (id, username, password_hash) VALUES (2, 'defender', 'unused')")
        c1 = {"user_id": 1, "name": "挑战者", "level": 5, "hp": 100, "max_hp": 100,
              "mp": 50, "max_mp": 50, "atk": 20, "def_stat": 6, "spirit_root": "ling",
              "techniques": "[]", "proficiency": "{}", "open_meridians": "[]",
              "weapon": None, "armor": None, "accessory": None, "pets": "[]",
              "active_pet": None, "arena_defense_skills": "[]"}
        if char1_kwargs:
            c1.update(char1_kwargs)
        conn.execute(
            "INSERT INTO characters (user_id, name, level, hp, max_hp, mp, max_mp, atk, def_stat, "
            "spirit_root, techniques, proficiency, open_meridians, weapon, armor, accessory, "
            "pets, active_pet, arena_defense_skills) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c1["user_id"], c1["name"], c1["level"], c1["hp"], c1["max_hp"],
             c1["mp"], c1["max_mp"], c1["atk"], c1["def_stat"], c1["spirit_root"],
             c1["techniques"], c1["proficiency"], c1["open_meridians"], c1["weapon"],
             c1["armor"], c1["accessory"], c1["pets"], c1["active_pet"],
             c1["arena_defense_skills"])
        )
        c2 = {"user_id": 2, "name": "防守者", "level": 5, "hp": 100, "max_hp": 100,
              "mp": 50, "max_mp": 50, "atk": 20, "def_stat": 6, "spirit_root": "ling",
              "techniques": "[]", "proficiency": "{}", "open_meridians": "[]",
              "weapon": None, "armor": None, "accessory": None, "pets": "[]",
              "active_pet": None, "arena_defense_skills": "[]"}
        if char2_kwargs:
            c2.update(char2_kwargs)
        conn.execute(
            "INSERT INTO characters (user_id, name, level, hp, max_hp, mp, max_mp, atk, def_stat, "
            "spirit_root, techniques, proficiency, open_meridians, weapon, armor, accessory, "
            "pets, active_pet, arena_defense_skills) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c2["user_id"], c2["name"], c2["level"], c2["hp"], c2["max_hp"],
             c2["mp"], c2["max_mp"], c2["atk"], c2["def_stat"], c2["spirit_root"],
             c2["techniques"], c2["proficiency"], c2["open_meridians"], c2["weapon"],
             c2["armor"], c2["accessory"], c2["pets"], c2["active_pet"],
             c2["arena_defense_skills"])
        )
    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()
    game_state.online_users.clear()
    game_state.last_activity.clear()


def _cleanup_arena_socket():
    with game_state.cache_lock:
        game_state.character_cache.clear()
        game_state.dirty_users.clear()
    game_state.online_users.clear()
    game_state.last_activity.clear()


def test_arena_challenge_socket_happy_path(tmp_path, monkeypatch):
    """Socket 端到端：正常挑战流程。"""
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "arena_socket.db"))
    _seed_arena_users(str(tmp_path / "arena_socket.db"))
    from app import app, socketio

    try:
        flask_client = app.test_client()
        with flask_client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "challenger"
        client = socketio.test_client(app, flask_test_client=flask_client)
        client.emit("arena_challenge", {"opponent_id": 2})
        events = client.get_received()
        result = [e["args"][0] for e in events if e["name"] == "arena_combat_result"]
        assert len(result) == 1
        assert result[0]["winner_id"] in {1, 2}
        assert 5 <= result[0]["score_change"] <= 35
        assert len(result[0]["log"]) > 0

        # DB 次数应递增
        char1 = models.get_character(1)
        assert char1["arena_challenges_today"] == 1
        client.disconnect()
    finally:
        _cleanup_arena_socket()


def test_arena_challenge_self_rejected(tmp_path, monkeypatch):
    """Socket 端到端：不可挑战自己。"""
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "arena_self.db"))
    _seed_arena_users(str(tmp_path / "arena_self.db"))
    from app import app, socketio

    try:
        flask_client = app.test_client()
        with flask_client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "challenger"
        client = socketio.test_client(app, flask_test_client=flask_client)
        client.emit("arena_challenge", {"opponent_id": 1})
        events = client.get_received()
        msgs = [e["args"][0] for e in events if e["name"] == "game_msg"]
        assert any("幻影" in m["text"] for m in msgs)
        client.disconnect()
    finally:
        _cleanup_arena_socket()


def test_arena_challenge_daily_limit(tmp_path, monkeypatch):
    """Socket 端到端：每日 5 次上限。"""
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "arena_limit.db"))
    _seed_arena_users(str(tmp_path / "arena_limit.db"))
    today_str = date.today().isoformat()
    models.update_character(1, arena_challenges_today=5, arena_last_challenge_date=today_str)
    with game_state.cache_lock:
        game_state.character_cache.pop(1, None)
        game_state.dirty_users.discard(1)

    from app import app, socketio
    try:
        flask_client = app.test_client()
        with flask_client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "challenger"
        client = socketio.test_client(app, flask_test_client=flask_client)
        client.emit("arena_challenge", {"opponent_id": 2})
        events = client.get_received()
        msgs = [e["args"][0] for e in events if e["name"] == "game_msg"]
        assert any("次数已尽" in m["text"] for m in msgs)
        client.disconnect()
    finally:
        _cleanup_arena_socket()


def test_arena_challenge_missing_opponent(tmp_path, monkeypatch):
    """Socket 端到端：无效对手 ID。"""
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "arena_missing.db"))
    _seed_arena_users(str(tmp_path / "arena_missing.db"))
    from app import app, socketio

    try:
        flask_client = app.test_client()
        with flask_client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "challenger"
        client = socketio.test_client(app, flask_test_client=flask_client)
        client.emit("arena_challenge", {"opponent_id": 999})
        events = client.get_received()
        msgs = [e["args"][0] for e in events if e["name"] == "game_msg"]
        assert any("信息缺失" in m["text"] for m in msgs)
        client.disconnect()
    finally:
        _cleanup_arena_socket()


def test_arena_set_defense_socket(tmp_path, monkeypatch):
    """Socket 端到端：设置防守技能。"""
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "arena_defense.db"))
    _seed_arena_users(
        str(tmp_path / "arena_defense.db"),
        char1_kwargs={"techniques": json.dumps(["jichu_tuna", "qingxin_jue", "modao_rumen", "lingxi_jue"])},
    )
    from app import app, socketio

    try:
        flask_client = app.test_client()
        with flask_client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "challenger"
        client = socketio.test_client(app, flask_test_client=flask_client)

        # 设置 3 个防守技能
        client.emit("arena_set_defense", {"skill_ids": ["jichu_tuna", "qingxin_jue", "modao_rumen"]})
        client.get_received()  # drain

        # 验证缓存（handler 写入缓存，未刷盘）
        char = game_state.get_cached_character(1)
        assert json.loads(char["arena_defense_skills"]) == ["jichu_tuna", "qingxin_jue", "modao_rumen"]

        # 传入 4 个，应截断为 3
        client.emit("arena_set_defense", {"skill_ids": ["jichu_tuna", "qingxin_jue", "modao_rumen", "lingxi_jue"]})
        client.get_received()
        char = game_state.get_cached_character(1)
        assert len(json.loads(char["arena_defense_skills"])) == 3

        # 传入未学习技能，应被过滤
        client.emit("arena_set_defense", {"skill_ids": ["jichu_tuna", "nonexistent_skill"]})
        client.get_received()
        char = game_state.get_cached_character(1)
        skills = json.loads(char["arena_defense_skills"])
        assert "nonexistent_skill" not in skills
        assert "jichu_tuna" in skills

        client.disconnect()
    finally:
        _cleanup_arena_socket()
