import sqlite3
from datetime import datetime, timedelta
from config import ADMIN_IDS

DB_NAME = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            sub_until TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vk_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT UNIQUE,
            name TEXT,
            friends_count INTEGER,
            is_valid BOOLEAN DEFAULT 1,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_metrics (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            earnings REAL DEFAULT 0.0,
            successful_broadcasts INTEGER DEFAULT 0,
            failed_broadcasts INTEGER DEFAULT 0
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO bot_metrics (id, earnings, successful_broadcasts, failed_broadcasts) VALUES (1, 0.0, 0, 0)")
    conn.commit()
    conn.close()

def add_or_update_user(user_id: int, username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def is_sub_active(user_id: int) -> bool:
    if ADMIN_IDS and user_id in ADMIN_IDS:
        return True
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT sub_until FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return False
    return datetime.fromisoformat(row[0]) > datetime.now()

def set_subscription(user_id: int, days: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT sub_until FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    now = datetime.now()
    base_time = datetime.fromisoformat(row[0]) if (row and row[0] and datetime.fromisoformat(row[0]) > now) else now
    new_sub = base_time + timedelta(days=days)
    cursor.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (new_sub.isoformat(), user_id))
    conn.commit()
    conn.close()

def add_earnings(amount: float):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_metrics SET earnings = earnings + ? WHERE id = 1", (amount,))
    conn.commit()
    conn.close()

def add_broadcast_stats(success: int, errors: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_metrics SET successful_broadcasts = successful_broadcasts + ?, failed_broadcasts = failed_broadcasts + ? WHERE id = 1", (success, errors))
    conn.commit()
    conn.close()

def get_bot_metrics():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT earnings, successful_broadcasts, failed_broadcasts FROM bot_metrics WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"earnings": row[0], "success": row[1], "errors": row[2]}
    return {"earnings": 0.0, "success": 0, "errors": 0}

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM vk_accounts")
    accs_count = cursor.fetchone()[0]
    metrics = get_bot_metrics()
    conn.close()
    return {
        "users": users_count,
        "accounts": accs_count,
        "earnings": metrics["earnings"],
        "success_bc": metrics["success"],
        "fail_bc": metrics["errors"]
    }

def save_vk_account(user_id: int, token: str, name: str, friends: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO vk_accounts (user_id, token, name, friends_count, is_valid)
        VALUES (?, ?, ?, ?, 1)
    """, (user_id, token, name, friends))
    conn.commit()
    conn.close()

def get_user_vk_accounts(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, token, name, friends_count, is_valid FROM vk_accounts WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "token": r[1], "name": r[2], "friends": r[3], "is_valid": bool(r[4])} for r in rows]

def clear_user_vk_accounts(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vk_accounts WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

init_db()