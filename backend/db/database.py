import json
import aiosqlite
from config import settings

class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or settings.DB_PATH
        self._db = None

    async def connect(self):
        if self._db is not None:
            return
        settings.ensure_dirs()
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._init_tables()

    async def update_last_message_metadata(self, session_id: str, role: str, metadata: dict):
        """更新最近一条消息的 metadata（用于追加 segments）"""
        cursor = await self._db.execute(
            "SELECT id, metadata FROM conversations WHERE session_id = ? AND role = ? ORDER BY id DESC LIMIT 1",
            (session_id, role)
        )
        row = await cursor.fetchone()
        if row:
            msg_id = row[0]
            try:
                old_meta = json.loads(row[1] or "{}")
            except (json.JSONDecodeError, TypeError):
                old_meta = {}
            old_meta.update(metadata)
            await self._db.execute(
                "UPDATE conversations SET metadata = ? WHERE id = ?",
                (json.dumps(old_meta, ensure_ascii=False), msg_id)
            )
            await self._db.commit()

    async def update_message_metadata_by_generation(self, session_id: str, role: str, generation_id: str, metadata: dict):
        """更新指定生成对应的消息 metadata。"""
        cursor = await self._db.execute(
            "SELECT id, metadata FROM conversations "
            "WHERE session_id = ? AND role = ? ORDER BY id DESC",
            (session_id, role),
        )
        rows = await cursor.fetchall()
        for row in rows:
            try:
                old_meta = json.loads(row[1] or "{}")
            except (json.JSONDecodeError, TypeError):
                old_meta = {}
            if old_meta.get("generation_id") != generation_id:
                continue
            old_meta.update(metadata)
            await self._db.execute(
                "UPDATE conversations SET metadata = ? WHERE id = ?",
                (json.dumps(old_meta, ensure_ascii=False), row[0]),
            )
            await self._db.commit()
            return True
        return False

    async def close(self):
        if self._db:
            connection = self._db
            self._db = None
            await connection.close()

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                persona TEXT DEFAULT 'default',
                metadata TEXT DEFAULT '{}',
                client_message_id TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id);

            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        await self._db.commit()

        columns = await self._db.execute("PRAGMA table_info(conversations)")
        column_names = {row[1] for row in await columns.fetchall()}
        if "client_message_id" not in column_names:
            await self._db.execute(
                "ALTER TABLE conversations ADD COLUMN client_message_id TEXT DEFAULT NULL"
            )
        await self._db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_client_message "
            "ON conversations(client_message_id) WHERE client_message_id IS NOT NULL"
        )
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS chat_requests (
                client_message_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                generation_id TEXT NOT NULL,
                request_type TEXT NOT NULL DEFAULT 'message',
                status TEXT NOT NULL DEFAULT 'accepted',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_requests_generation "
            "ON chat_requests(generation_id)"
        )
        await self._db.commit()

        # session_metadata table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS session_metadata (
                session_id TEXT PRIMARY KEY,
                name TEXT DEFAULT '',
                theme_pack_id TEXT DEFAULT 'default_pack'
            )
        """)
        await self._db.commit()

        # memories table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                source TEXT DEFAULT 'auto',
                expired_at TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.commit()

        # summaries table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                content TEXT NOT NULL,
                msg_from INTEGER,
                msg_to INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.commit()

    async def get_session_meta(self, session_id):
        cursor = await self._db.execute(
            "SELECT session_id, name, theme_pack_id FROM session_metadata WHERE session_id = ?",
            (session_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {"session_id": row[0], "name": row[1], "theme_pack_id": row[2]}
        return {"session_id": session_id, "name": "", "theme_pack_id": "default_pack"}

    async def set_session_meta(self, session_id, name=None, theme_pack_id=None):
        meta = await self.get_session_meta(session_id)
        if name is not None:
            meta["name"] = name
        if theme_pack_id is not None:
            meta["theme_pack_id"] = theme_pack_id
        await self._db.execute(
            "INSERT OR REPLACE INTO session_metadata (session_id, name, theme_pack_id) VALUES (?, ?, ?)",
            (session_id, meta["name"], meta["theme_pack_id"])
        )
        await self._db.commit()

    async def save_message(self, session_id: str, role: str, content: str, persona: str = "default", metadata: str = "{}", segments: list = None, client_message_id: str = None):
        meta = json.loads(metadata) if isinstance(metadata, str) else (metadata or {})
        if segments:
            meta["segments"] = segments
        metadata_str = json.dumps(meta, ensure_ascii=False)
        cursor = await self._db.execute(
            "INSERT OR IGNORE INTO conversations "
            "(session_id, role, content, persona, metadata, client_message_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, role, content, persona, metadata_str, client_message_id)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def get_message_by_client_id(self, client_message_id: str):
        if not client_message_id:
            return None
        cursor = await self._db.execute(
            "SELECT id, session_id, role, content, persona, metadata, client_message_id "
            "FROM conversations WHERE client_message_id = ?",
            (client_message_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def record_chat_request(self, client_message_id: str, session_id: str, generation_id: str, request_type: str):
        cursor = await self._db.execute(
            "INSERT OR IGNORE INTO chat_requests "
            "(client_message_id, session_id, generation_id, request_type, status) "
            "VALUES (?, ?, ?, ?, 'accepted')",
            (client_message_id, session_id, generation_id, request_type)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def get_chat_request(self, client_message_id: str):
        if not client_message_id:
            return None
        cursor = await self._db.execute(
            "SELECT client_message_id, session_id, generation_id, request_type, status "
            "FROM chat_requests WHERE client_message_id = ?",
            (client_message_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_chat_request_status(self, generation_id: str, status: str):
        await self._db.execute(
            "UPDATE chat_requests SET status = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE generation_id = ?",
            (status, generation_id)
        )
        await self._db.commit()

    async def delete_messages_from(self, session_id: str, message_id: int):
        """删除指定 ID 及之后的所有消息（用于编辑/重新生成）"""
        await self._db.execute(
            "DELETE FROM conversations WHERE session_id = ? AND id >= ?",
            (session_id, message_id)
        )
        await self._db.commit()

    async def get_last_user_message(self, session_id: str) -> dict | None:
        """获取最后一条用户消息"""
        cursor = await self._db.execute(
            "SELECT id, role, content, metadata FROM conversations WHERE session_id = ? AND role = 'user' ORDER BY id DESC LIMIT 1",
            (session_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_history(self, session_id: str, limit: int = 50):
        cursor = await self._db.execute(
            "SELECT id, role, content, persona, metadata, client_message_id, created_at "
            "FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = await cursor.fetchall()
        result = []
        for row in reversed(rows):
            d = dict(row)
            try:
                meta = json.loads(d.get("metadata", "{}"))
                if "segments" in meta:
                    d["segments"] = meta["segments"]
                if "generation_id" in meta:
                    d["generation_id"] = meta["generation_id"]
            except (json.JSONDecodeError, TypeError):
                pass
            result.append(d)
        return result

    async def get_config(self, key: str, default: str = ""):
        cursor = await self._db.execute("SELECT value FROM app_config WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else default

    async def set_config(self, key: str, value: str):
        await self._db.execute(
            "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)", (key, value)
        )
        await self._db.commit()

    # --- Memory methods ---

    async def get_memories(self, limit=20, category=None):
        """获取长期记忆，按权重+时间综合排序，排除已过期的"""
        # 权重：instruction=3 > fact=2 > preference=1 > general=0
        weight_case = "CASE category WHEN 'instruction' THEN 3 WHEN 'fact' THEN 2 WHEN 'preference' THEN 1 ELSE 0 END"
        query = f"SELECT id, content, category, source, expired_at, created_at FROM memories WHERE (expired_at IS NULL OR expired_at > datetime('now'))"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        query += f" ORDER BY {weight_case} DESC, created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await self._db.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]

    async def save_memory(self, content, category='general', source='auto', expired_at=None):
        await self._db.execute(
            "INSERT INTO memories (content, category, source, expired_at) VALUES (?, ?, ?, ?)",
            (content, category, source, expired_at)
        )
        await self._db.commit()

    async def update_memory(self, memory_id, content=None, category=None):
        if content:
            await self._db.execute("UPDATE memories SET content = ? WHERE id = ?", (content, memory_id))
        if category:
            await self._db.execute("UPDATE memories SET category = ? WHERE id = ?", (category, memory_id))
        await self._db.commit()

    async def delete_memory(self, memory_id):
        await self._db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        await self._db.commit()

    async def delete_expired_memories(self):
        await self._db.execute("DELETE FROM memories WHERE expired_at IS NOT NULL AND expired_at <= datetime('now')")
        await self._db.commit()

    async def check_duplicate_memory(self, content):
        """检查是否有相似记忆（字符串包含匹配）"""
        cursor = await self._db.execute("SELECT id, content FROM memories")
        rows = await cursor.fetchall()
        for row in rows:
            existing = row['content']
            if content in existing or existing in content:
                return row['id']
        return None

    # --- Summary methods ---

    async def get_summaries(self, session_id, level=None):
        query = "SELECT id, session_id, level, content, msg_from, msg_to FROM summaries WHERE session_id = ?"
        params = [session_id]
        if level is not None:
            query += " AND level = ?"
            params.append(level)
        query += " ORDER BY msg_from ASC"
        cursor = await self._db.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]

    async def save_summary(self, session_id, content, msg_from, msg_to, level=1):
        await self._db.execute(
            "INSERT INTO summaries (session_id, level, content, msg_from, msg_to) VALUES (?, ?, ?, ?, ?)",
            (session_id, level, content, msg_from, msg_to)
        )
        await self._db.commit()

    async def delete_summaries(self, ids):
        if not ids:
            return
        placeholders = ','.join('?' * len(ids))
        await self._db.execute(f"DELETE FROM summaries WHERE id IN ({placeholders})", ids)
        await self._db.commit()

    async def get_summary_count(self, session_id):
        cursor = await self._db.execute("SELECT COUNT(*) FROM summaries WHERE session_id = ?", (session_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_message_count(self, session_id):
        cursor = await self._db.execute("SELECT COUNT(*) FROM conversations WHERE session_id = ?", (session_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_uncovered_history(self, session_id, limit=10):
        """获取未被摘要覆盖的历史消息"""
        covered_to = 0
        cursor = await self._db.execute(
            "SELECT MAX(msg_to) FROM summaries WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if row and row[0]:
            covered_to = row[0]

        cursor = await self._db.execute(
            "SELECT id, role, content FROM conversations WHERE session_id = ? AND id > ? ORDER BY id ASC LIMIT ?",
            (session_id, covered_to, limit)
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def get_uncovered_message_count(self, session_id):
        """获取未被摘要覆盖的消息数量"""
        covered_to = 0
        cursor = await self._db.execute(
            "SELECT MAX(msg_to) FROM summaries WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if row and row[0]:
            covered_to = row[0]

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM conversations WHERE session_id = ? AND id > ?",
            (session_id, covered_to)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

db = Database()
