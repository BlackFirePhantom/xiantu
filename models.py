"""数据库模型与操作函数（SQLite）"""

import sqlite3
import json
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger("xiantu.db")

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "game.db")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _column_exists(conn, table, column):
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)


# 数据库迁移：每条迁移按版本号顺序执行，失败则跳过（已执行过的）
_MIGRATIONS = [
    # (版本号, 列名, 表, 列定义)
    (1, "spirit_root",       "characters", "TEXT DEFAULT NULL"),
    (2, "techniques",        "characters", "TEXT DEFAULT '[]'"),
    (3, "open_meridians",    "characters", "TEXT DEFAULT '[]'"),
    (4, "last_active",       "characters", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    (5, "accessory",         "characters", "TEXT DEFAULT NULL"),
    (6, "combat_buff",       "characters", "INTEGER DEFAULT 0"),
    (7, "pets",              "characters", "TEXT DEFAULT '[]'"),
    (8, "active_pet",        "characters", "TEXT DEFAULT NULL"),
    (9, "npc_goodwill",      "characters", "TEXT DEFAULT '{}'"),
    (10, "active_quests",    "characters", "TEXT DEFAULT '[]'"),
    (11, "completed_quests", "characters", "TEXT DEFAULT '[]'"),
    (12, "sect_contrib",     "characters", "INTEGER DEFAULT 0"),
    (13, "daily_quest_date", "characters", "TEXT DEFAULT NULL"),
    (14, "npc_gift_date",    "characters", "TEXT DEFAULT '{}'"),
    (15, "proficiency",      "characters", "TEXT DEFAULT '{}'"),
    (16, "mp",               "characters", "INTEGER DEFAULT 50"),
    (17, "max_mp",           "characters", "INTEGER DEFAULT 50"),
]


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                atk INTEGER DEFAULT 10,
                def_stat INTEGER DEFAULT 5,
                gold INTEGER DEFAULT 50,
                location TEXT DEFAULT 'qingyun_town',
                weapon TEXT DEFAULT NULL,
                armor TEXT DEFAULT NULL,
                inventory TEXT DEFAULT '{}',
                kills INTEGER DEFAULT 0,
                deaths INTEGER DEFAULT 0,
                has_breakthrough_pill INTEGER DEFAULT 0,
                spirit_root TEXT DEFAULT NULL,
                techniques TEXT DEFAULT '[]',
                open_meridians TEXT DEFAULT '[]',
                pets TEXT DEFAULT '[]',
                active_pet TEXT DEFAULT NULL,
                npc_goodwill TEXT DEFAULT '{}',
                active_quests TEXT DEFAULT '[]',
                completed_quests TEXT DEFAULT '[]',
                sect_contrib INTEGER DEFAULT 0,
                daily_quest_date TEXT DEFAULT NULL,
                npc_gift_date TEXT DEFAULT '{}',
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS secret_realm_runs (
                week_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                explorations INTEGER NOT NULL DEFAULT 0,
                contribution INTEGER NOT NULL DEFAULT 0,
                boss_damage INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (week_id, user_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS secret_realm_bosses (
                week_id TEXT PRIMARY KEY,
                hp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL
            );
        """)

        # 获取当前版本
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_version").fetchall()}

        for ver, col, table, col_def in _MIGRATIONS:
            if ver in applied:
                continue
            if not _column_exists(conn, table, col):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                logger.info("数据库迁移 v%d：%s 表新增列 %s", ver, table, col)
            conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (?)", (ver,))


def create_user(username, password_hash):
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_user(username):
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def create_character(user_id, name, spirit_root):
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO characters (user_id, name, spirit_root, last_active) VALUES (?, ?, ?, datetime('now'))",
                (user_id, name, spirit_root),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_character(user_id):
    with get_db() as conn:
        return conn.execute("SELECT * FROM characters WHERE user_id = ?", (user_id,)).fetchone()


def update_character(user_id, **kwargs):
    if not kwargs:
        return
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    with get_db() as conn:
        conn.execute(f"UPDATE characters SET {set_clause} WHERE user_id = ?", values)


def get_secret_realm_run(user_id, week_id):
    """Return a player's progress for one realm rotation, creating it if needed."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO secret_realm_runs (week_id, user_id) VALUES (?, ?)",
            (week_id, user_id),
        )
        row = conn.execute(
            "SELECT explorations, contribution, boss_damage FROM secret_realm_runs "
            "WHERE week_id = ? AND user_id = ?",
            (week_id, user_id),
        ).fetchone()
    return dict(row)


def save_secret_realm_run(user_id, week_id, *, explorations, contribution, boss_damage):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO secret_realm_runs (week_id, user_id, explorations, contribution, boss_damage)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(week_id, user_id) DO UPDATE SET
                   explorations = excluded.explorations,
                   contribution = excluded.contribution,
                   boss_damage = excluded.boss_damage""",
            (week_id, user_id, explorations, contribution, boss_damage),
        )


def get_secret_realm_boss(week_id, max_hp=500):
    """Return the shared realm boss, creating the week's boss on first access."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO secret_realm_bosses (week_id, hp, max_hp) VALUES (?, ?, ?)",
            (week_id, max_hp, max_hp),
        )
        row = conn.execute(
            "SELECT hp, max_hp FROM secret_realm_bosses WHERE week_id = ?", (week_id,)
        ).fetchone()
    return dict(row)


def save_secret_realm_boss(week_id, *, hp):
    with get_db() as conn:
        conn.execute("UPDATE secret_realm_bosses SET hp = ? WHERE week_id = ?", (hp, week_id))


def get_secret_realm_leaderboard(week_id, limit=10):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT c.name, r.contribution, r.boss_damage
               FROM secret_realm_runs r
               JOIN characters c ON c.user_id = r.user_id
               WHERE r.week_id = ?
               ORDER BY r.contribution DESC, r.boss_damage DESC, c.name ASC
               LIMIT ?""",
            (week_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_character_inventory(user_id):
    char = get_character(user_id)
    if char:
        return json.loads(char["inventory"]) if char["inventory"] else {}
    return {}


def set_character_inventory(user_id, inventory):
    update_character(user_id, inventory=json.dumps(inventory))


def get_leaderboard(limit=20):
    with get_db() as conn:
        return conn.execute(
            "SELECT name, level, exp, kills FROM characters ORDER BY level DESC, exp DESC LIMIT ?",
            (limit,),
        ).fetchall()


def get_online_count():
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM characters").fetchone()
        return row["cnt"] if row else 0
