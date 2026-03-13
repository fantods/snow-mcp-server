from typing import Any

from snow.config import CONTEXT_KEY_PATTERN, ENTRY_TYPES, MAX_CONTENT_SIZE
from snow.db import Database
from snow.models import (
    DeleteResult,
    Memory,
    MemoryListResult,
    StoreResult,
    UpdateResult,
)


class ValidationError(Exception):
    pass


class NotFoundError(Exception):
    pass


class MemoryService:
    def __init__(self, db: Database):
        self._db = db

    def _validate_context_key(self, context_key: str) -> None:
        if not CONTEXT_KEY_PATTERN.match(context_key):
            raise ValidationError(
                f"Invalid context_key: must be 'global' or 'project:<name>'. Got: {context_key}"
            )

    def _validate_entry_type(self, entry_type: str) -> None:
        if entry_type not in ENTRY_TYPES:
            raise ValidationError(
                f"Invalid entry_type: must be one of {ENTRY_TYPES}. Got: {entry_type}"
            )

    def _validate_content_size(self, content: str) -> None:
        if len(content) > MAX_CONTENT_SIZE:
            raise ValidationError(
                f"Content exceeds {MAX_CONTENT_SIZE} bytes limit. Got: {len(content)} bytes."
            )

    def _validate_metadata(
        self, entry_type: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        from snow.models import METADATA_SCHEMAS

        schema_cls = METADATA_SCHEMAS.get(entry_type)
        if schema_cls is None:
            return metadata

        try:
            validated = schema_cls(**metadata)
            return validated.model_dump()
        except Exception as e:
            raise ValidationError(
                f"Invalid metadata for entry_type '{entry_type}': {e}"
            )

    async def store(
        self,
        context_key: str,
        entry_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> StoreResult:
        self._validate_context_key(context_key)
        self._validate_entry_type(entry_type)
        self._validate_content_size(content)

        validated_metadata = self._validate_metadata(entry_type, metadata or {})

        memory = await self._db.store(
            context_key=context_key,
            entry_type=entry_type,
            content=content,
            metadata=validated_metadata,
        )

        return StoreResult(id=memory.id, created_at=memory.created_at)

    async def recall(self, context_key: str) -> MemoryListResult:
        self._validate_context_key(context_key)
        memories = await self._db.recall(context_key)
        return MemoryListResult(memories=memories)

    async def search(
        self,
        query: str,
        context_key: str | None = None,
    ) -> MemoryListResult:
        if context_key is not None:
            self._validate_context_key(context_key)

        memories = await self._db.search(query, context_key)
        return MemoryListResult(memories=memories)

    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UpdateResult:
        if content is not None:
            self._validate_content_size(content)

        existing = await self._db.get_by_id(memory_id)
        if existing is None:
            raise NotFoundError(f"Memory not found: {memory_id}")
        if existing.deleted_at is not None:
            raise NotFoundError(f"Memory was deleted: {memory_id}")

        if metadata is not None:
            metadata = self._validate_metadata(existing.entry_type, metadata)

        updated = await self._db.update(memory_id, content, metadata)
        if updated is None:
            raise NotFoundError(f"Memory not found: {memory_id}")

        return UpdateResult(id=updated.id, updated_at=updated.updated_at)

    async def delete(
        self,
        memory_id: str,
        permanent: bool = False,
    ) -> DeleteResult:
        if permanent:
            deleted = await self._db.hard_delete(memory_id)
        else:
            deleted = await self._db.soft_delete(memory_id)

        return DeleteResult(
            id=memory_id,
            deleted=deleted,
            permanent=permanent,
        )

    async def get(self, memory_id: str) -> Memory:
        memory = await self._db.get_by_id(memory_id)
        if memory is None:
            raise NotFoundError(f"Memory not found: {memory_id}")
        if memory.deleted_at is not None:
            raise NotFoundError(f"Memory was deleted: {memory_id}")
        return memory
