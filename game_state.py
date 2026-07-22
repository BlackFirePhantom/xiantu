"""共享内存状态模块，用于在子 Handler 和 app 之间共享全局数据，并提供内存缓存与延迟挂机计算功能。"""

import time
import json
import logging
import threading
import models

# 导入配置和游戏常数
from config import AFK_TIMEOUT
from game_data import IDLE_EXP_PER_SEC, IDLE_MAX_HOURS

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

# 战斗状态（回合制）
active_combats = {}     # user_id -> combat_state dict
combat_lock = threading.Lock()
COMBAT_TIMEOUT = 300   # 战斗超时（秒），5 分钟无操作自动中断

# 秘境行动按玩家串行化。SQLite 事务保证最终结算原子性；此锁避免同一玩家
# 的两个 Socket 事件在计算技能、增益和法力值时读取到同一份旧回合状态。
secret_realm_locks = {}
secret_realm_locks_guard = threading.Lock()

# SocketIO 实例引用（由 app.py 启动时注入）
socketio = None

# 写回（Write-Back）缓存核心设计
character_cache = {}   # user_id -> character dict (可写)
dirty_users = set()    # 存有脏数据的 user_id 集合
cache_lock = threading.RLock()


def get_secret_realm_lock(user_id):
    """Return a stable per-player lock for secret realm actions."""
    with secret_realm_locks_guard:
        lock = secret_realm_locks.get(user_id)
        if lock is None:
            lock = threading.RLock()
            secret_realm_locks[user_id] = lock
        return lock

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


def refresh_cached_character(user_id):
    """Replace a cached character with its current database row.

    Use this after an atomic model operation that updates character fields
    directly, so later state payloads cannot overwrite or expose stale data.
    """
    row = models.get_character(user_id)
    with cache_lock:
        if not row:
            character_cache.pop(user_id, None)
            dirty_users.discard(user_id)
            return None

        char_dict = dict(row)
        character_cache[user_id] = char_dict
        dirty_users.discard(user_id)
        return char_dict

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
    """挂机收益的惰性延迟结算具体逻辑。

    使用 ``game.cultivation.compute_idle_reward`` 与离线路径共享同一套收益逻辑
    （修为 + 材料掉落 + 安全区回血），确保两条路径产出一致。
    """
    user = models.get_user(username)
    if not user:
        return

    char = get_cached_character(user["id"])
    if not char:
        return

    from game.cultivation import compute_idle_reward
    from game_data import ITEMS
    from game.utils import get_full_stats, format_duration

    reward = compute_idle_reward(char, idle_duration)

    # 写入掉落物品到背包
    if reward["drops"]:
        inv = get_character_inventory_cached(user["id"])
        for item_id in reward["drops"]:
            inv[item_id] = inv.get(item_id, 0) + 1
        set_character_inventory_cached(user["id"], inv)

    # 更新经验（满级时 exp=0，自动跳过）
    if reward["exp"] > 0:
        update_cached_character(user["id"], exp=char["exp"] + reward["exp"])

    # 安全区自动回血
    if reward["heal_to_full"]:
        stats = get_full_stats(char)
        update_cached_character(user["id"], hp=stats["max_hp"])

    # 通知客户端
    sid = online_users.get(username)
    if socketio and sid:
        socketio.emit("afk_status", {"afk": False}, room=sid)
        socketio.emit("afk_tick", {
            "exp": reward["exp"],
            "drops": [ITEMS[d]["name"] for d in reward["drops"] if d in ITEMS],
            "duration": format_duration(reward["elapsed"]),
        }, room=sid)


def cleanup_stale_combats():
    """扫描并清理超时的战斗状态。

    遍历 ``active_combats``，将 ``last_action_at`` 距今超过 ``COMBAT_TIMEOUT``
    的战斗弹出并持久化当前 HP（防止免费满血逃脱）。若玩家在线则发送
    ``combat_end`` 通知前端关闭面板。
    """
    now = time.time()
    stale = []
    with combat_lock:
        for uid, combat in list(active_combats.items()):
            last = combat.get("last_action_at", 0)
            if now - last > COMBAT_TIMEOUT:
                stale.append((uid, combat))

    for uid, combat in stale:
        with combat_lock:
            # 再次确认仍在 dict 中（防止与 do_fight_action 并发）
            if active_combats.get(uid) is not combat:
                continue
            active_combats.pop(uid, None)

        # 持久化当前战斗 HP（与逃跑路径一致）
        update_cached_character(uid, hp=combat["player_hp"])
        save_cached_character(uid)

        # 若玩家在线，通知前端关闭战斗面板
        username = combat.get("username", "")
        sid = online_users.get(username) if username else None
        if socketio and sid:
            socketio.emit("combat_end", {
                "won": False,
                "fled": False,
                "log": ["战斗因长时间未操作已中断。"],
            }, room=sid)
        logger.info("清理超时战斗：user_id=%s, username=%s", uid, username)


def reset_combats():
    """清空所有战斗状态（仅用于测试）。"""
    with combat_lock:
        active_combats.clear()
