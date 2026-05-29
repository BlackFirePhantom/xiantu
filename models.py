"""数据库模型与操作函数（SQLite）"""

import sqlite3
import json
import os
from contextlib import contextmanager

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
        """)
        # 兼容旧数据库：自动添加新列
        for col, col_def in [
            ("spirit_root", "TEXT DEFAULT NULL"),
            ("techniques", "TEXT DEFAULT '[]'"),
            ("open_meridians", "TEXT DEFAULT '[]'"),
            ("last_active", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("accessory", "TEXT DEFAULT NULL"),
            ("combat_buff", "INTEGER DEFAULT 0"),
            ("pets", "TEXT DEFAULT '[]'"),
            ("active_pet", "TEXT DEFAULT NULL"),
            ("npc_goodwill", "TEXT DEFAULT '{}'"),
            ("active_quests", "TEXT DEFAULT '[]'"),
            ("completed_quests", "TEXT DEFAULT '[]'"),
            ("sect_contrib", "INTEGER DEFAULT 0"),
            ("daily_quest_date", "TEXT DEFAULT NULL"),
            ("npc_gift_date", "TEXT DEFAULT '{}'"),
        ]:
            if not _column_exists(conn, "characters", col):
                conn.execute(f"ALTER TABLE characters ADD COLUMN {col} {col_def}")


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
