# memory.py
import sqlite3

DB_PATH = "laws/conversation_memory.db" # Путь к БД

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
        # Получаем максимальный индекс для текущей сессии, чтобы добавить сообщение
        # Проверяем, существует ли уже такая запись, чтобы избежать дубликатов при OR REPLACE
        # Если это первый вызов после стриминга, то записи еще нет
        # Если это повторный вызов (например, при отладке), OR REPLACE обновит
        
        # Получаем количество сообщений для этой сессии
        count = conn.execute(
            "SELECT COUNT(*) FROM memory WHERE session_id=?",
            (session_id,)
        ).fetchone()[0]

        conn.execute(
            "INSERT OR REPLACE INTO memory VALUES (?, ?, ?, ?)",
            (session_id, count, role, content) # Используем count как index
        )
        conn.commit()

def load_conversation(session_id):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT role, content FROM memory WHERE session_id=? ORDER BY message_index",
            (session_id,)
        ).fetchall()
        return [{"role": role, "parts": [content]} for role, content in rows]

def delete_conversation(session_id):
    """Удаляет всю историю сообщений для указанной сессии."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM memory WHERE session_id=?",
            (session_id,)
        )
        conn.commit()
