import sqlite3
from typing import List, Dict, Any

class SQLiteHistoryManager:
    def __init__(self, db_path: str = "chat_history.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Inicializa las tablas solicitadas con su esquema exacto."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Tabla de Chats
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    nombre TEXT
                )
            """)
            # 2. Tabla de Mensajes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(chat_id) REFERENCES chats(id)
                )
            """)
            conn.commit()

    def ensure_chat_exists(self, chat_id: str, nombre: str = "Nueva Consulta de IA"):
        """Asegura la existencia de la sesión de chat."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO chats (id, nombre) VALUES (?, ?)", (chat_id, nombre))
            conn.commit()

    def save_message(self, chat_id: str, role: str, content: str):
        """Guarda automáticamente un mensaje en la base de datos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (chat_id, role, content) 
                VALUES (?, ?, ?)
            """, (chat_id, role, content))
            conn.commit()

    def get_chat_history_str(self, chat_id: str, limit: int = 10) -> str:
        """Recupera el historial y lo formatea como un string para el contexto del LLM."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content FROM messages 
                WHERE chat_id = ? 
                ORDER BY timestamp ASC 
                LIMIT ?
            """, (chat_id, limit))
            rows = cursor.fetchall()
            
            if not rows:
                return "No hay historial previo."
            
            history_lines = []
            for role, content in rows:
                user_label = "Usuario" if role == "user" else "Agente"
                history_lines.append(f"{user_label}: {content}")
            
            return "\n".join(history_lines)