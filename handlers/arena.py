import json
import logging
from datetime import date
from flask import session, request
from flask_socketio import emit

import game_state
from game_state import (
    get_cached_character as get_character,
    update_cached_character as update_character,
    refresh_cached_character
)
import models
from game_data import TECHNIQUES, realm_name
from game.arena import simulate_pvp

logger = logging.getLogger("xiantu.handlers.arena")

def _get_player_skills(char):
    """获取玩家已学功法中的可用技能列表"""
    try:
        learned = json.loads(char["techniques"]) if char["techniques"] else []
    except Exception:
        learned = []
    skills = []
    for tid in learned:
        t = TECHNIQUES.get(tid)
        if t and t.get("skill"):
            skills.append({"tech_id": tid, "name": t["name"], "skill": t["skill"]})
    return skills

def register_arena_handlers(socketio):
    @socketio.on("get_arena")
    def handle_get_arena():
        if "user_id" not in session:
            return
        user_id = session["user_id"]
        username = session.get("username", "")
        game_state.touch_activity(username)
        
        char = get_character(user_id)
        if not char:
            return
            
        today_str = date.today().isoformat()
        challenges = char.get("arena_challenges_today", 0) or 0
        if char.get("arena_last_challenge_date") != today_str:
            challenges = 0
            update_character(user_id, arena_challenges_today=0, arena_last_challenge_date=today_str)
            char = get_character(user_id) # reload
            
        opponents = models.get_arena_opponents(user_id)
        for opp in opponents:
            opp["realm"] = realm_name(opp["level"])
            
        leaderboard = models.get_arena_leaderboard(10)
        for lb in leaderboard:
            lb["realm"] = realm_name(lb["level"])
            
        logs = models.get_arena_logs(user_id)
        all_skills = _get_player_skills(char)
        
        # 组装防守技能配置
        def_skills_raw = char.get("arena_defense_skills", "[]")
        try:
            defense_skills = json.loads(def_skills_raw) if def_skills_raw else []
        except Exception:
            defense_skills = []
            
        emit("arena_state", {
            "score": char.get("arena_score", 1000) or 1000,
            "wins": char.get("arena_wins", 0) or 0,
            "losses": char.get("arena_losses", 0) or 0,
            "challenges_remaining": max(0, 5 - challenges),
            "defense_skills": defense_skills,
            "opponents": opponents,
            "logs": logs,
            "leaderboard": leaderboard,
            "all_skills": all_skills,
            "my_id": user_id,
            "my_name": char.get("name")
        })

    @socketio.on("arena_set_defense")
    def handle_arena_set_defense(data):
        if "user_id" not in session:
            return
        user_id = session["user_id"]
        game_state.touch_activity(session.get("username", ""))
        
        skill_ids = data.get("skill_ids", [])
        if not isinstance(skill_ids, list):
            emit("game_msg", {"text": "防守技能格式无效。", "type": "error"})
            return
            
        # 验证这几个技能是否全部已习得
        char = get_character(user_id)
        if not char:
            return
            
        try:
            learned = set(json.loads(char["techniques"]) if char["techniques"] else [])
        except Exception:
            learned = set()
            
        valid_ids = []
        for sid in skill_ids[:3]: # 最多3个
            if sid in learned and sid in TECHNIQUES:
                valid_ids.append(sid)
                
        update_character(user_id, arena_defense_skills=json.dumps(valid_ids))
        emit("game_msg", {"text": "论道防守套路配置完成！", "type": "success"})
        handle_get_arena() # 刷新面板

    @socketio.on("arena_challenge")
    def handle_arena_challenge(data):
        if "user_id" not in session:
            return
        user_id = session["user_id"]
        username = session.get("username", "")
        game_state.touch_activity(username)
        
        opponent_id = data.get("opponent_id")
        if not opponent_id:
            emit("game_msg", {"text": "未指定论道对手。", "type": "error"})
            return
            
        if opponent_id == user_id:
            emit("game_msg", {"text": "切莫与自身的幻影缠斗，此举无法证道。", "type": "error"})
            return
            
        char = get_character(user_id)
        opp = models.get_character(opponent_id)
        if not char or not opp:
            emit("game_msg", {"text": "论道双方信息缺失，无法开战。", "type": "error"})
            return
            
        # 检查次数
        today_str = date.today().isoformat()
        challenges = char.get("arena_challenges_today", 0) or 0
        if char.get("arena_last_challenge_date") != today_str:
            challenges = 0
            
        if challenges >= 5:
            emit("game_msg", {"text": "今日论道次数已尽，急于求成易生心魔，明日再来吧。", "type": "warning"})
            return
            
        # 开始模拟战斗
        winner_id, score_change, combat_log = simulate_pvp(char, dict(opp))
        
        # 写入数据库并更新属性
        res = models.update_arena_result(user_id, opponent_id, winner_id, score_change, combat_log)
        if not res.get("ok"):
            emit("game_msg", {"text": f"论道结算失败：{res.get('reason')}", "type": "error"})
            return
            
        # 刷新缓存（极其关键：写入数据库后必须从DB刷新缓存）
        refresh_cached_character(user_id)
        refresh_cached_character(opponent_id)
        
        # 发送挑战结果
        emit("arena_combat_result", {
            "winner_id": winner_id,
            "score_change": score_change,
            "log": combat_log
        })
        
        # 刷新自身论道面板
        handle_get_arena()
        
        # 如果防守方在线，通知防守方刷新
        # 获取防守方 username
        with models.get_db() as conn:
            user_row = conn.execute("SELECT username FROM users WHERE id = ?", (opponent_id,)).fetchone()
            if user_row:
                opp_username = user_row["username"]
                opp_sid = game_state.online_users.get(opp_username)
                if opp_sid:
                    # 向防守方在线连接广播更新通知
                    socketio.emit("arena_state_changed", {}, room=opp_sid)
