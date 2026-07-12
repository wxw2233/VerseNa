import aiosqlite
from config import settings

class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or settings.DB_PATH
        self._db = None

    async def connect(self):
        settings.ensure_dirs()
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._init_tables()

    async def close(self):
        if self._db:
            await self._db.close()

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                persona TEXT DEFAULT 'default',
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id);

            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        await self._db.commit()

    async def save_message(self, session_id: str, role: str, content: str, persona: str = "default", metadata: str = "{}"):
        await self._db.execute(
            "INSERT INTO conversations (session_id, role, content, persona, metadata) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, persona, metadata)
        )
        await self._db.commit()

    async def get_history(self, session_id: str, limit: int = 50):
        cursor = await self._db.execute(
            "SELECT role, content, persona, metadata, created_at FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in reversed(rows)]

    async def get_config(self, key: str, default: str = ""):
        cursor = await self._db.execute("SELECT value FROM app_config WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else default

    async def set_config(self, key: str, value: str):
        await self._db.execute(
            "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)", (key, value)
        )
        await self._db.commit()

db = Database()
