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
    """Raised when input validation fails."""

    pass


class NotFoundError(Exception):
    """Raised when a requested memory is not found or has been deleted."""

    pass


class MemoryService:
    """
    High-level service for managing persistent memories.

    Provides validation, business logic, and orchestration between the MCP
    interface and the database layer. All input is validated before being
    persisted to ensure data integrity.
    """

    def __init__(self, db: Database):
        """
        Initialize the memory service.

        Args:
            db: Database instance for persistence operations.
        """
        self._db = db

    def _validate_context_key(self, context_key: str) -> None:
        """
        Validate that context_key matches the expected pattern.

        Args:
            context_key: The context key to validate.

        Raises:
            ValidationError: If context_key is not 'global' or 'project:<name>'.
        """
        if not CONTEXT_KEY_PATTERN.match(context_key):
            raise ValidationError(
                f"Invalid context_key: must be 'global' or 'project:<name>'. Got: {context_key}"
            )

    def _validate_entry_type(self, entry_type: str) -> None:
        """
        Validate that entry_type is one of the allowed types.

        Args:
            entry_type: The entry type to validate.

        Raises:
            ValidationError: If entry_type is not in ENTRY_TYPES.
        """
        if entry_type not in ENTRY_TYPES:
            raise ValidationError(
                f"Invalid entry_type: must be one of {ENTRY_TYPES}. Got: {entry_type}"
            )

    def _validate_content_size(self, content: str) -> None:
        """
        Validate that content does not exceed the maximum size limit.

        Args:
            content: The content string to validate.

        Raises:
            ValidationError: If content exceeds MAX_CONTENT_SIZE bytes.
        """
        if len(content) > MAX_CONTENT_SIZE:
            raise ValidationError(
                f"Content exceeds {MAX_CONTENT_SIZE} bytes limit. Got: {len(content)} bytes."
            )

    def _validate_metadata(
        self, entry_type: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate metadata against the schema for the given entry_type.

        Args:
            entry_type: The entry type to get the schema for.
            metadata: The metadata dictionary to validate.

        Returns:
            Validated metadata as a dictionary.

        Raises:
            ValidationError: If metadata does not match the schema.
        """
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
        """
        Store a new memory in the database.

        Args:
            context_key: Memory context - 'global' or 'project:<name>'.
            entry_type: Type of memory - 'preference', 'instruction', 'snippet', or 'context'.
            content: The memory content to store (max 8KB).
            metadata: Optional typed metadata validated against entry_type schema.

        Returns:
            StoreResult containing the new memory's ID and creation timestamp.

        Raises:
            ValidationError: If any input fails validation.
        """
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
        """
        Recall all non-deleted memories for a specific context.

        Args:
            context_key: Memory context to recall from - 'global' or 'project:<name>'.

        Returns:
            MemoryListResult containing all memories for the context.

        Raises:
            ValidationError: If context_key is invalid.
        """
        self._validate_context_key(context_key)
        memories = await self._db.recall(context_key)
        return MemoryListResult(memories=memories)

    async def search(
        self,
        query: str,
        context_key: str | None = None,
    ) -> MemoryListResult:
        """
        Search memories by content using full-text search or LIKE pattern.

        Uses FTS5 for queries of 3+ characters, falls back to LIKE for shorter queries.

        Args:
            query: Search query string.
            context_key: Optional context to filter search results.

        Returns:
            MemoryListResult containing matching memories.

        Raises:
            ValidationError: If context_key is provided and invalid.
        """
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
        """
        Update an existing memory's content and/or metadata.

        Args:
            memory_id: UUID of the memory to update.
            content: Optional new content (max 8KB).
            metadata: Optional new metadata (validated against existing entry_type).

        Returns:
            UpdateResult containing the memory ID and update timestamp.

        Raises:
            ValidationError: If content exceeds size limit or metadata is invalid.
            NotFoundError: If memory doesn't exist or has been deleted.
        """
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
        """
        Delete a memory from the database.

        Args:
            memory_id: UUID of the memory to delete.
            permanent: If True, permanently remove from database. If False, soft delete.

        Returns:
            DeleteResult indicating whether deletion succeeded.
        """
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
        """
        Retrieve a specific memory by ID.

        Args:
            memory_id: UUID of the memory to retrieve.

        Returns:
            The requested Memory object.

        Raises:
            NotFoundError: If memory doesn't exist or has been deleted.
        """
        memory = await self._db.get_by_id(memory_id)
        if memory is None:
            raise NotFoundError(f"Memory not found: {memory_id}")
        if memory.deleted_at is not None:
            raise NotFoundError(f"Memory was deleted: {memory_id}")
        return memory
