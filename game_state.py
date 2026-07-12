"""共享内存状态模块，用于在子 Handler 和 app 之间共享全局数据，并提供内存缓存与延迟挂机计算功能。"""

import time
import json
import logging
import threading
import models

# 导入配置和游戏常数
from config import AFK_TIMEOUT, AFK_MAX_HOURS, AFK_INTERVAL
from game_data import IDLE_EXP_PER_SEC

logger = logging.getLogger("xiantu.game_state")

# 玩家连接与活动状态
online_users = {}      # username -> sid
last_activity = {}     # username -> timestamp of last action
afk_players = {}       # username -> timestamp when AFK started
afk_lock = threading.Lock()  # 保护 touch_activity 的 check-then-act 序列

# 拍卖行状态
active_auctions = {}   # auction_id -> auction_detail
auction_npc_state = {} # NPC 竞拍预算等状态，由 app.py 初始化
auction_last_refresh = 0
AUCTION_REFRESH_INTERVAL = 4 * 3600 * 1000  # 4小时(ms)

# SocketIO 实例引用（由 app.py 启动时注入）
socketio = None

# 写回（Write-Back）缓存核心设计
character_cache = {}   # user_id -> character dict (可写)
dirty_users = set()    # 存有脏数据的 user_id 集合
cache_lock = threading.RLock()

def get_cached_character(user_id):
    """从内存缓存获取角色数据。若未命中，则从 SQLite 加载并转为 dict。"""
    with cache_lock:
        if user_id in character_cache:
            return character_cache[user_id]
        
        row = models.get_character(user_id)
        if row:
            char_dict = dict(row)
            character_cache[user_id] = char_dict
            return char_dict
        return None

def update_cached_character(user_id, **kwargs):
    """更新角色缓存，并将 user_id 标记为脏数据。"""
    if not kwargs:
        return
    with cache_lock:
        char = character_cache.get(user_id)
        if not char:
            row = models.get_character(user_id)
            if row:
                char = dict(row)
                character_cache[user_id] = char
            else:
                return
        
        char.update(kwargs)
        dirty_users.add(user_id)

def modify_cached_character(user_id, **field_deltas):
    """原子地增减角色字段值（解决 read-modify-write 竞态）。

    典型用法::

        # 旧写法（有竞态）：char = get_cached_character(uid); update_cached_character(uid, exp=char["exp"]+50)
        # 新写法（原子）：  modify_cached_character(uid, exp=50)

    参数:
        user_id: 用户 ID
        **field_deltas: {字段名: 增量}，正数增加，负数减少

    返回:
        {字段名: 更新后的值} 字典，角色不存在时返回 None
    """
    if not field_deltas:
        return None
    with cache_lock:
        char = character_cache.get(user_id)
        if not char:
            row = models.get_character(user_id)
            if row:
                char = dict(row)
                character_cache[user_id] = char
            else:
                return None
        result = {}
        for field, delta in field_deltas.items():
            new_val = char.get(field, 0) + delta
            char[field] = new_val
            result[field] = new_val
        dirty_users.add(user_id)
        return result

def get_character_inventory_cached(user_id):
    """获取角色的背包（优先命中缓存，保持 100% 外界兼容性）"""
    char = get_cached_character(user_id)
    if char:
        return json.loads(char["inventory"]) if char["inventory"] else {}
    return {}

def set_character_inventory_cached(user_id, inventory):
    """设置角色的背包（写入内存缓存，暂不提交到 SQLite）"""
    update_cached_character(user_id, inventory=json.dumps(inventory))

def save_cached_character(user_id):
    """将单个角色的脏缓存数据强行刷盘，并将其从内存中释放（用于用户下线时）"""
    with cache_lock:
        if user_id in character_cache:
            if user_id in dirty_users:
                char_data = character_cache[user_id]
                # 剔除只读 ID 和外键，避免 SQLite 主键更新开销或报错
                db_data = {k: v for k, v in char_data.items() if k not in ("id", "user_id")}
                try:
                    models.update_character(user_id, **db_data)
                except Exception as e:
                    logger.error("单个同步玩家 %s 缓存失败: %s", user_id, str(e))
                dirty_users.discard(user_id)
            character_cache.pop(user_id, None)

def flush_all_cache():
    """定时批处理：遍历所有脏缓存，批量更新回 SQLite 数据库。"""
    with cache_lock:
        if not dirty_users:
            return
        
        logger.info("开始定时同步缓存脏数据到数据库，待同步玩家数：%d", len(dirty_users))
        flushed = list(dirty_users)
        for user_id in flushed:
            if user_id in character_cache:
                char_data = character_cache[user_id]
                db_data = {k: v for k, v in char_data.items() if k not in ("id", "user_id")}
                try:
                    models.update_character(user_id, **db_data)
                    dirty_users.discard(user_id)
                except Exception as e:
                    logger.error("批量同步玩家 %s 缓存失败: %s", user_id, str(e))
        logger.info("定时同步缓存任务结束")

def touch_activity(username):
    """记录用户活动时间，若达到挂机阈值则触发惰性延迟结算。"""
    if not username:
        return
    now = time.time()

    # 加锁保护 check-then-act，防止并发双重结算
    need_settle = False
    idle_duration = 0
    with afk_lock:
        if username in last_activity:
            idle_duration = now - last_activity[username]
            if idle_duration >= AFK_TIMEOUT:
                # 先更新时间再结算，阻止后续并发事件重复触发
                last_activity[username] = now
                need_settle = True
            else:
                last_activity[username] = now
        else:
            last_activity[username] = now

    if need_settle:
        _settle_afk_reward(username, idle_duration)

def _settle_afk_reward(username, idle_duration):
    """挂机收益的惰性延迟结算具体逻辑。"""
    max_duration = AFK_MAX_HOURS * 3600
    gain_seconds = min(idle_duration, max_duration)
    
    user = models.get_user(username)
    if not user:
        return
    
    char = get_cached_character(user["id"])
    if not char:
        return
        
    from game_data import LOCATIONS, ITEMS
    from game.utils import get_cultivation_mult, get_full_stats, format_duration, get_exp_needed
    import random
    
    loc = LOCATIONS.get(char["location"], LOCATIONS["qingyun_town"])
    mult = get_cultivation_mult(char)
    exp_gain = int(IDLE_EXP_PER_SEC * gain_seconds * mult)
    
    # 模拟概率掉落
    drops = []
    if not loc["safe"]:
        # 每隔 AFK_INTERVAL (10秒) 有 30% 几率掉落一个材料
        # 为了防循环过大，上限限制尝试次数为 150 次
        attempts = min(150, int(gain_seconds / AFK_INTERVAL))
        mat_pool = ["lingcao", "yaogu", "yaopimo", "hantie_kuang"]
        for _ in range(attempts):
            if random.random() < 0.3:
                drops.append(random.choice(mat_pool))
                
    # 写入背包
    inv = get_character_inventory_cached(user["id"])
    for item_id in drops:
        inv[item_id] = inv.get(item_id, 0) + 1
    set_character_inventory_cached(user["id"], inv)
    
    # 更新经验（char 引用已在上方获取，缓存返回的是同一 dict）
    if get_exp_needed(char["level"]) != "-":
        update_cached_character(user["id"], exp=char["exp"] + exp_gain)
        
    # 安全区自动回血
    if loc["safe"]:
        stats = get_full_stats(char)
        update_cached_character(user["id"], hp=stats["max_hp"])
        
    # 通知客户端
    sid = online_users.get(username)
    if socketio and sid:
        socketio.emit("afk_status", {"afk": False}, room=sid)
        socketio.emit("afk_tick", {
            "exp": exp_gain,
            "drops": [ITEMS[d]["name"] for d in drops],
            "duration": format_duration(int(gain_seconds)),
        }, room=sid)
