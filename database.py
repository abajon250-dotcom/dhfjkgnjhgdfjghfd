import sqlite3
import datetime

DB_NAME = "database.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            joined_date TEXT,
            subscription_until TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vk_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT,
            name TEXT,
            friends INTEGER
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        now = datetime.datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO users (user_id, joined_date, subscription_until) VALUES (?, ?, ?)", 
            (user_id, now, None)
        )
        conn.commit()
    conn.close()

def get_user_subscription(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT subscription_until FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not row["subscription_until"]:
        return {"active": False, "expire_str": "❌ Не оформлена"}
    
    try:
        expire_dt = datetime.datetime.fromisoformat(row["subscription_until"])
        if datetime.datetime.now() < expire_dt:
            return {
                "active": True,
                "expire_dt": expire_dt,
                "expire_str": expire_dt.strftime("%d.%m.%Y в %H:%M")
            }
    except Exception:
        pass
        
    return {"active": False, "expire_str": "⏳ Истекла"}

def extend_subscription(user_id: int, days: int = 30):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT subscription_until FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    now = datetime.datetime.now()
    base_time = now
    
    if row and row["subscription_until"]:
        try:
            current_expire = datetime.datetime.fromisoformat(row["subscription_until"])
            if current_expire > now:
                base_time = current_expire
        except Exception:
            pass
            
    new_expire = base_time + datetime.timedelta(days=days)
    
    cursor.execute("""
        INSERT INTO users (user_id, joined_date, subscription_until) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET subscription_until = ?
    """, (user_id, now.isoformat(), new_expire.isoformat(), new_expire.isoformat()))
    
    conn.commit()
    conn.close()
    return new_expire.strftime("%d.%m.%Y в %H:%M")

def save_vk_account(user_id: int, token: str, name: str, friends: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO vk_accounts (user_id, token, name, friends) 
        VALUES (?, ?, ?, ?)
    """, (user_id, token, name, friends))
    conn.commit()
    conn.close()

def get_user_vk_accounts(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, friends, token FROM vk_accounts WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows
