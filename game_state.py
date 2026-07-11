"""共享内存状态模块，用于在子 Handler 和 app 之间共享全局数据，避免循环导入。"""

import time

# 玩家连接与活动状态
online_users = {}      # username -> sid
last_activity = {}     # username -> timestamp of last action
afk_players = {}       # username -> timestamp when AFK started

# 拍卖行状态
active_auctions = {}   # auction_id -> auction_detail
auction_npc_state = {} # NPC 竞拍预算等状态，由 app.py 初始化
auction_last_refresh = 0
AUCTION_REFRESH_INTERVAL = 4 * 3600 * 1000  # 4小时(ms)

# SocketIO 实例引用（由 app.py 启动时注入）
socketio = None

def touch_activity(username):
    """记录用户活动时间"""
    if not username:
        return
    last_activity[username] = time.time()
    if username in afk_players:
        del afk_players[username]
        if socketio:
            socketio.emit("afk_status", {"afk": False}, room=online_users.get(username))
