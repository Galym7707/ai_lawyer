# memory.py
import sqlite3

DB_PATH = "laws/conversation_memory.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            session_id TEXT,
            message_index INTEGER,
            role TEXT,
            content TEXT,
            PRIMARY KEY(session_id, message_index)
        )
        """)

def save_message(session_id, role, content):
    with sqlite3.connect(DB_PATH) as conn:
        index = conn.execute(
            "SELECT COUNT(*) FROM memory WHERE session_id=?",
            (session_id,)
        ).fetchone()[0]
        # Защита от дубликатов при повторном вызове
        conn.execute(
            "INSERT OR REPLACE INTO memory VALUES (?, ?, ?, ?)",
            (session_id, index, role, content)
        )
        conn.commit()

def load_conversation(session_id):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT role, content FROM memory WHERE session_id=? ORDER BY message_index",
            (session_id,)
        ).fetchall()
        return [{"role": role, "parts": [content]} for role, content in rows]
