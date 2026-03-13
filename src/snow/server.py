from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from snow.db import Database
from snow.service import MemoryService, NotFoundError, ValidationError


@dataclass
class AppContext:
    db: Database
    service: MemoryService


@asynccontextmanager
async def lifespan(app: FastMCP):
    db = await Database.connect()
    service = MemoryService(db)
    yield AppContext(db=db, service=service)
    await db.close()


mcp = FastMCP(
    name="Snow",
    instructions="Snow is a persistent memory server for AI agents. Store and recall preferences, instructions, snippets, and context across sessions.",
    lifespan=lifespan,
)


def _get_service(ctx: Context) -> MemoryService:
    return ctx.request_context.lifespan_context.service


@mcp.tool()
async def store_memory(
    context_key: str,
    entry_type: str,
    content: str,
    metadata: dict[str, Any] | None,
    ctx: Context,
) -> dict[str, Any]:
    """Store a new memory in the database.

    Args:
        context_key: Memory context - 'global' or 'project:<name>'
        entry_type: Type of memory - 'preference', 'instruction', 'snippet', or 'context'
        content: The memory content (max 8KB)
        metadata: Optional typed metadata based on entry_type

    Returns:
        The created memory ID and timestamp
    """
    service = _get_service(ctx)
    try:
        result = await service.store(
            context_key=context_key,
            entry_type=entry_type,
            content=content,
            metadata=metadata,
        )
        return result.model_dump()
    except ValidationError as e:
        return {"error": str(e)}


@mcp.tool()
async def recall_memory(
    context_key: str,
    ctx: Context,
) -> dict[str, Any]:
    """Recall memories for a specific context.

    Args:
        context_key: Memory context - 'global' or 'project:<name>'

    Returns:
        List of memories for the given context
    """
    service = _get_service(ctx)
    try:
        result = await service.recall(context_key=context_key)
        return result.model_dump()
    except ValidationError as e:
        return {"error": str(e)}


@mcp.tool()
async def search_memories(
    query: str,
    context_key: str | None,
    ctx: Context,
) -> dict[str, Any]:
    """Search memories by content using FTS5 or LIKE.

    Args:
        query: Search query (uses FTS5 for 3+ chars, LIKE for shorter)
        context_key: Optional context to filter results

    Returns:
        List of matching memories
    """
    service = _get_service(ctx)
    try:
        result = await service.search(
            query=query,
            context_key=context_key,
        )
        return result.model_dump()
    except ValidationError as e:
        return {"error": str(e)}


@mcp.tool()
async def update_memory(
    id: str,
    content: str | None,
    metadata: dict[str, Any] | None,
    ctx: Context,
) -> dict[str, Any]:
    """Update an existing memory.

    Args:
        id: UUID of the memory to update
        content: New content (optional, max 8KB)
        metadata: New metadata (optional, validated against entry_type schema)

    Returns:
        Updated memory ID and timestamp
    """
    service = _get_service(ctx)
    try:
        result = await service.update(
            memory_id=id,
            content=content,
            metadata=metadata,
        )
        return result.model_dump()
    except ValidationError as e:
        return {"error": str(e)}
    except NotFoundError as e:
        return {"error": str(e)}


@mcp.tool()
async def delete_memory(
    id: str,
    permanent: bool,
    ctx: Context,
) -> dict[str, Any]:
    """Delete a memory (soft delete by default).

    Args:
        id: UUID of the memory to delete
        permanent: If True, permanently remove from database (default False)

    Returns:
        Deletion confirmation with id and permanent flag
    """
    service = _get_service(ctx)
    result = await service.delete(
        memory_id=id,
        permanent=permanent,
    )
    return result.model_dump()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
