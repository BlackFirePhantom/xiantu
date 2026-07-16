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
    (18, "settlement_claimed", "secret_realm_runs", "INTEGER DEFAULT 0"),
    (19, "titles", "characters", "TEXT DEFAULT '[]'"),
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

            CREATE TABLE IF NOT EXISTS sect_bosses (
                week_id TEXT PRIMARY KEY,
                hp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sect_boss_runs (
                week_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                damage INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (week_id, user_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
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


def apply_secret_realm_boss_damage(user_id, week_id, requested_damage, max_hp=500):
    """Atomically settle one hit against the shared weekly boss.

    The immediate transaction serializes competing final hits so the unique reward
    cannot be issued twice.
    """
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR IGNORE INTO secret_realm_bosses (week_id, hp, max_hp) VALUES (?, ?, ?)",
            (week_id, max_hp, max_hp),
        )
        conn.execute(
            "INSERT OR IGNORE INTO secret_realm_runs (week_id, user_id) VALUES (?, ?)",
            (week_id, user_id),
        )
        boss = conn.execute(
            "SELECT hp FROM secret_realm_bosses WHERE week_id = ?", (week_id,)
        ).fetchone()
        if boss["hp"] <= 0:
            return {"ok": False, "reason": "boss_defeated"}

        damage = min(max(1, int(requested_damage)), boss["hp"])
        remaining_hp = boss["hp"] - damage
        defeated = remaining_hp == 0
        conn.execute("UPDATE secret_realm_bosses SET hp = ? WHERE week_id = ?", (remaining_hp, week_id))
        conn.execute(
            """UPDATE secret_realm_runs
               SET contribution = contribution + ?, boss_damage = boss_damage + ?
               WHERE week_id = ? AND user_id = ?""",
            (damage, damage, week_id, user_id),
        )

        char = conn.execute(
            "SELECT sect_contrib, inventory FROM characters WHERE user_id = ?", (user_id,)
        ).fetchone()
        if char:
            inventory = json.loads(char["inventory"]) if char["inventory"] else {}
            if defeated:
                inventory["chiyan_jing"] = inventory.get("chiyan_jing", 0) + 1
            conn.execute(
                "UPDATE characters SET sect_contrib = ?, inventory = ? WHERE user_id = ?",
                (char["sect_contrib"] + damage, json.dumps(inventory), user_id),
            )

    return {
        "ok": True,
        "damage": damage,
        "boss_hp": remaining_hp,
        "defeated": defeated,
        "reward_granted": defeated,
    }


def resolve_secret_realm_boss_encounter(
    user_id, week_id, *, player_damage, player_defense, boss_attack, max_hp, entry_limit
):
    """Atomically resolve one realm-boss strike and its counterattack."""
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR IGNORE INTO secret_realm_bosses (week_id, hp, max_hp) VALUES (?, ?, ?)",
            (week_id, max_hp, max_hp),
        )
        conn.execute(
            "INSERT OR IGNORE INTO secret_realm_runs (week_id, user_id) VALUES (?, ?)",
            (week_id, user_id),
        )
        run = conn.execute(
            "SELECT explorations FROM secret_realm_runs WHERE week_id = ? AND user_id = ?",
            (week_id, user_id),
        ).fetchone()
        if run["explorations"] >= entry_limit:
            return {"ok": False, "reason": "no_entries"}

        boss = conn.execute(
            "SELECT hp FROM secret_realm_bosses WHERE week_id = ?", (week_id,)
        ).fetchone()
        if boss["hp"] <= 0:
            return {"ok": False, "reason": "boss_defeated"}

        char = conn.execute(
            "SELECT hp, max_hp, deaths, location, sect_contrib, inventory FROM characters WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not char:
            return {"ok": False, "reason": "character_missing"}

        damage = min(max(1, int(player_damage)), boss["hp"])
        remaining_hp = boss["hp"] - damage
        defeated = remaining_hp == 0
        counter_damage = 0 if defeated else max(1, int(boss_attack) - int(player_defense))
        player_hp = max(0, char["hp"] - counter_damage)
        player_died = player_hp == 0
        restored_hp = max(1, char["max_hp"] // 2) if player_died else player_hp
        inventory = json.loads(char["inventory"]) if char["inventory"] else {}
        if defeated:
            inventory["chiyan_jing"] = inventory.get("chiyan_jing", 0) + 1

        conn.execute("UPDATE secret_realm_bosses SET hp = ? WHERE week_id = ?", (remaining_hp, week_id))
        entry_consumed = player_died or defeated
        conn.execute(
            """UPDATE secret_realm_runs
               SET explorations = explorations + ?, contribution = contribution + ?, boss_damage = boss_damage + ?
             WHERE week_id = ? AND user_id = ?""",
            (int(entry_consumed), damage, damage, week_id, user_id),
        )
        conn.execute(
            """UPDATE characters
               SET hp = ?, deaths = ?, location = ?, sect_contrib = ?, inventory = ?
               WHERE user_id = ?""",
            (
                restored_hp,
                char["deaths"] + int(player_died),
                "qingyun_town" if player_died else char["location"],
                char["sect_contrib"] + damage,
                json.dumps(inventory),
                user_id,
            ),
        )

    return {
        "ok": True,
        "damage": damage,
        "boss_hp": remaining_hp,
        "defeated": defeated,
        "reward_granted": defeated,
        "player_damage": counter_damage,
        "player_hp": restored_hp,
        "player_died": player_died,
        "entry_consumed": entry_consumed,
        "entries_remaining": entry_limit - run["explorations"] - int(entry_consumed),
    }


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


def claim_secret_realm_settlement(user_id, week_id):
    """Award one participant's weekly ranking reward exactly once."""
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute(
            "SELECT contribution, settlement_claimed FROM secret_realm_runs WHERE week_id = ? AND user_id = ?",
            (week_id, user_id),
        ).fetchone()
        if not run or run["contribution"] <= 0:
            return {"ok": False, "reason": "not_participant"}
        if run["settlement_claimed"]:
            return {"ok": False, "reason": "already_claimed"}

        rank = conn.execute(
            """SELECT COUNT(*) + 1 FROM secret_realm_runs
               WHERE week_id = ? AND (contribution > ? OR (contribution = ? AND boss_damage >
                   (SELECT boss_damage FROM secret_realm_runs WHERE week_id = ? AND user_id = ?)))""",
            (week_id, run["contribution"], run["contribution"], week_id, user_id),
        ).fetchone()[0]
        gold_reward = 20 + {1: 50, 2: 30, 3: 15}.get(rank, 0)
        conn.execute(
            "UPDATE secret_realm_runs SET settlement_claimed = 1 WHERE week_id = ? AND user_id = ?",
            (week_id, user_id),
        )
        title_reward = None
        if rank == 1:
            title_reward = f"赤焰征服者·{week_id}"
            char = conn.execute("SELECT titles FROM characters WHERE user_id = ?", (user_id,)).fetchone()
            titles = json.loads(char["titles"]) if char and char["titles"] else []
            if title_reward not in titles:
                titles.append(title_reward)
                conn.execute("UPDATE characters SET titles = ? WHERE user_id = ?", (json.dumps(titles), user_id))
        conn.execute("UPDATE characters SET gold = gold + ? WHERE user_id = ?", (gold_reward, user_id))
    result = {"ok": True, "week_id": week_id, "rank": rank, "gold_reward": gold_reward}
    if title_reward:
        result["title_reward"] = title_reward
    return result


def get_pending_secret_realm_settlements(user_id, current_week_id):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT week_id, contribution FROM secret_realm_runs
               WHERE user_id = ? AND contribution > 0 AND settlement_claimed = 0 AND week_id < ?
               ORDER BY week_id DESC""",
            (user_id, current_week_id),
        ).fetchall()
    return [dict(row) for row in rows]


def get_character_titles(user_id):
    char = get_character(user_id)
    if not char or not char["titles"]:
        return []
    return json.loads(char["titles"])


def get_sect_boss(week_id, max_hp=1200):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sect_bosses (week_id, hp, max_hp) VALUES (?, ?, ?)",
            (week_id, max_hp, max_hp),
        )
        row = conn.execute("SELECT hp, max_hp FROM sect_bosses WHERE week_id = ?", (week_id,)).fetchone()
    return dict(row)


def apply_sect_boss_damage(user_id, week_id, requested_damage, max_hp=1200):
    """Atomically apply one player's contribution to the shared sect boss."""
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR IGNORE INTO sect_bosses (week_id, hp, max_hp) VALUES (?, ?, ?)",
            (week_id, max_hp, max_hp),
        )
        conn.execute(
            "INSERT OR IGNORE INTO sect_boss_runs (week_id, user_id) VALUES (?, ?)",
            (week_id, user_id),
        )
        boss = conn.execute("SELECT hp FROM sect_bosses WHERE week_id = ?", (week_id,)).fetchone()
        if boss["hp"] <= 0:
            return {"ok": False, "reason": "boss_defeated"}

        damage = min(max(1, int(requested_damage)), boss["hp"])
        remaining_hp = boss["hp"] - damage
        defeated = remaining_hp == 0
        conn.execute("UPDATE sect_bosses SET hp = ? WHERE week_id = ?", (remaining_hp, week_id))
        conn.execute(
            "UPDATE sect_boss_runs SET damage = damage + ? WHERE week_id = ? AND user_id = ?",
            (damage, week_id, user_id),
        )
        char = conn.execute(
            "SELECT sect_contrib, inventory FROM characters WHERE user_id = ?", (user_id,)
        ).fetchone()
        if char:
            inventory = json.loads(char["inventory"]) if char["inventory"] else {}
            if defeated:
                inventory["zongmen_lingpai"] = inventory.get("zongmen_lingpai", 0) + 1
            conn.execute(
                "UPDATE characters SET sect_contrib = ?, inventory = ? WHERE user_id = ?",
                (char["sect_contrib"] + damage, json.dumps(inventory), user_id),
            )

    return {
        "ok": True,
        "damage": damage,
        "boss_hp": remaining_hp,
        "defeated": defeated,
        "reward_granted": defeated,
    }


def get_sect_boss_leaderboard(week_id, limit=10):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT c.name, r.damage FROM sect_boss_runs r
               JOIN characters c ON c.user_id = r.user_id
               WHERE r.week_id = ? AND r.damage > 0
               ORDER BY r.damage DESC, c.name ASC LIMIT ?""",
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
