"""仙途配置管理"""

import os
import secrets

# 数据库
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "game.db")

# 安全配置
SECRET_KEY = os.environ.get("XIANTU_SECRET_KEY", "")
if not SECRET_KEY:
    _key_file = os.path.join(os.path.dirname(__file__), "data", ".secret_key")
    if os.path.exists(_key_file):
        with open(_key_file, "r") as f:
            SECRET_KEY = f.read().strip()
    if not SECRET_KEY:
        SECRET_KEY = secrets.token_hex(32)
        os.makedirs(os.path.dirname(_key_file), exist_ok=True)
        with open(_key_file, "w") as f:
            f.write(SECRET_KEY)

# CORS 配置
def parse_cors_origins(raw_origins):
    """Return a normalized allowlist, or ``None`` to keep Socket.IO same-origin."""
    if not raw_origins:
        return None
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return origins or None


CORS_ALLOWED_ORIGINS = parse_cors_origins(os.environ.get("XIANTU_CORS"))

# 服务器配置
HOST = os.environ.get("XIANTU_HOST", "0.0.0.0")
PORT = int(os.environ.get("XIANTU_PORT", "5000"))

# 挂机配置
AFK_TIMEOUT = 600       # 10分钟无操作进入挂机
AFK_MAX_HOURS = 24      # 挂机最大时长
AFK_INTERVAL = 60       # 挂机奖励间隔（秒）

# 拍卖行配置
AUCTION_REFRESH_INTERVAL = 4 * 3600 * 1000  # 4小时(ms)
