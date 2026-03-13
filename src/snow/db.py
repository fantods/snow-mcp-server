import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from snow.config import get_db_path
from snow.models import Memory

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    context_key TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_context_relevance 
    ON memories(context_key, updated_at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    content='memories',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) 
    VALUES('delete', old.rowid, old.content);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) 
    VALUES('delete', old.rowid, old.content);
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;

PRAGMA journal_mode=WAL;
"""


def _row_to_memory(row: aiosqlite.Row) -> Memory:
    return Memory(
        id=row["id"],
        context_key=row["context_key"],
        entry_type=row["entry_type"],
        content=row["content"],
        metadata=json.loads(row["metadata"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        deleted_at=datetime.fromisoformat(row["deleted_at"])
        if row["deleted_at"]
        else None,
    )


class Database:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    @classmethod
    async def connect(cls, db_path: Path | None = None) -> "Database":
        db = cls(db_path or get_db_path())
        db._conn = await aiosqlite.connect(db._db_path)
        db._conn.row_factory = aiosqlite.Row
        await db._conn.executescript(SCHEMA)
        return db

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def store(
        self,
        context_key: str,
        entry_type: str,
        content: str,
        metadata: dict,
    ) -> Memory:
        memory_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        metadata_json = json.dumps(metadata)

        await self._conn.execute(
            """
            INSERT INTO memories (id, context_key, entry_type, content, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_id, context_key, entry_type, content, metadata_json, now, now),
        )
        await self._conn.commit()

        return Memory(
            id=memory_id,
            context_key=context_key,
            entry_type=entry_type,
            content=content,
            metadata=metadata,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def recall(self, context_key: str) -> list[Memory]:
        cursor = await self._conn.execute(
            """
            SELECT * FROM memories 
            WHERE context_key = ? AND deleted_at IS NULL
            ORDER BY updated_at DESC
            """,
            (context_key,),
        )
        rows = await cursor.fetchall()
        return [_row_to_memory(row) for row in rows]

    async def search(
        self,
        query: str,
        context_key: str | None,
    ) -> list[Memory]:
        if len(query) < 3:
            return await self._search_like(query, context_key)
        return await self._search_fts(query, context_key)

    async def _search_like(
        self,
        query: str,
        context_key: str | None,
    ) -> list[Memory]:
        like_pattern = f"%{query}%"

        if context_key:
            cursor = await self._conn.execute(
                """
                SELECT * FROM memories 
                WHERE content LIKE ? AND context_key = ? AND deleted_at IS NULL
                ORDER BY updated_at DESC
                """,
                (like_pattern, context_key),
            )
        else:
            cursor = await self._conn.execute(
                """
                SELECT * FROM memories 
                WHERE content LIKE ? AND deleted_at IS NULL
                ORDER BY updated_at DESC
                """,
                (like_pattern,),
            )

        rows = await cursor.fetchall()
        return [_row_to_memory(row) for row in rows]

    async def _search_fts(
        self,
        query: str,
        context_key: str | None,
    ) -> list[Memory]:
        fts_query = f"{query}*"

        if context_key:
            cursor = await self._conn.execute(
                """
                SELECT m.* FROM memories m
                JOIN memories_fts fts ON m.rowid = fts.rowid
                WHERE memories_fts MATCH ? AND m.context_key = ? AND m.deleted_at IS NULL
                ORDER BY m.updated_at DESC
                """,
                (fts_query, context_key),
            )
        else:
            cursor = await self._conn.execute(
                """
                SELECT m.* FROM memories m
                JOIN memories_fts fts ON m.rowid = fts.rowid
                WHERE memories_fts MATCH ? AND m.deleted_at IS NULL
                ORDER BY m.updated_at DESC
                """,
                (fts_query,),
            )

        rows = await cursor.fetchall()
        return [_row_to_memory(row) for row in rows]

    async def get_by_id(self, memory_id: str) -> Memory | None:
        cursor = await self._conn.execute(
            "SELECT * FROM memories WHERE id = ?",
            (memory_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_memory(row)

    async def update(
        self,
        memory_id: str,
        content: str | None,
        metadata: dict | None,
    ) -> Memory | None:
        memory = await self.get_by_id(memory_id)
        if memory is None or memory.deleted_at is not None:
            return None

        now = datetime.now(UTC).isoformat()
        new_content = content if content is not None else memory.content
        new_metadata = metadata if metadata is not None else memory.metadata
        metadata_json = json.dumps(new_metadata)

        await self._conn.execute(
            """
            UPDATE memories SET content = ?, metadata = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_content, metadata_json, now, memory_id),
        )
        await self._conn.commit()

        return Memory(
            id=memory_id,
            context_key=memory.context_key,
            entry_type=memory.entry_type,
            content=new_content,
            metadata=new_metadata,
            created_at=memory.created_at,
            updated_at=datetime.fromisoformat(now),
        )

    async def soft_delete(self, memory_id: str) -> bool:
        memory = await self.get_by_id(memory_id)
        if memory is None or memory.deleted_at is not None:
            return False

        now = datetime.now(UTC).isoformat()
        await self._conn.execute(
            "UPDATE memories SET deleted_at = ? WHERE id = ?",
            (now, memory_id),
        )
        await self._conn.commit()
        return True

    async def hard_delete(self, memory_id: str) -> bool:
        cursor = await self._conn.execute(
            "DELETE FROM memories WHERE id = ?",
            (memory_id,),
        )
        await self._conn.commit()
        return cursor.rowcount > 0
