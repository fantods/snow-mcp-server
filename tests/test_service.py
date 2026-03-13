import pytest

from snow.service import MemoryService, ValidationError


@pytest.mark.asyncio
async def test_store_memory_valid(service: MemoryService):
    result = await service.store(
        context_key="global",
        entry_type="preference",
        content="Use 4-space indentation",
        metadata={"scope": "global", "priority": 10},
    )
    assert result.id is not None
    assert result.created_at is not None


@pytest.mark.asyncio
async def test_store_memory_invalid_context_key(service: MemoryService):
    with pytest.raises(ValidationError, match="Invalid context_key"):
        await service.store(
            context_key="invalid_key",
            entry_type="preference",
            content="test",
        )


@pytest.mark.asyncio
async def test_store_memory_invalid_entry_type(service: MemoryService):
    with pytest.raises(ValidationError, match="Invalid entry_type"):
        await service.store(
            context_key="global",
            entry_type="invalid_type",
            content="test",
        )


@pytest.mark.asyncio
async def test_store_memory_content_too_large(service: MemoryService):
    large_content = "x" * 9000
    with pytest.raises(ValidationError, match="exceeds"):
        await service.store(
            context_key="global",
            entry_type="preference",
            content=large_content,
        )


@pytest.mark.asyncio
async def test_store_memory_invalid_metadata(service: MemoryService):
    with pytest.raises(ValidationError, match="Invalid metadata"):
        await service.store(
            context_key="global",
            entry_type="preference",
            content="test",
            metadata={"priority": "not_a_number"},
        )


@pytest.mark.asyncio
async def test_recall_memory(service: MemoryService):
    await service.store(
        context_key="project:myapp",
        entry_type="instruction",
        content="Always use TypeScript strict mode",
    )

    result = await service.recall(context_key="project:myapp")

    assert len(result.memories) == 1
    assert result.memories[0].content == "Always use TypeScript strict mode"


@pytest.mark.asyncio
async def test_recall_memory_returns_all(service: MemoryService):
    for i in range(5):
        await service.store(
            context_key="global",
            entry_type="snippet",
            content=f"Snippet {i}",
        )

    result = await service.recall(context_key="global")
    assert len(result.memories) == 5


@pytest.mark.asyncio
async def test_search_memories_fts(service: MemoryService):
    await service.store(
        context_key="global",
        entry_type="instruction",
        content="Use React hooks for state management",
    )
    await service.store(
        context_key="global",
        entry_type="preference",
        content="Prefer functional components",
    )

    result = await service.search(query="React")

    assert len(result.memories) == 1
    assert "React" in result.memories[0].content


@pytest.mark.asyncio
async def test_search_memories_like(service: MemoryService):
    await service.store(
        context_key="global",
        entry_type="preference",
        content="Use dark theme",
    )

    result = await service.search(query="da")

    assert len(result.memories) == 1
    assert "dark" in result.memories[0].content


@pytest.mark.asyncio
async def test_search_memories_with_context_filter(service: MemoryService):
    await service.store(
        context_key="project:app1",
        entry_type="instruction",
        content="Use PostgreSQL database",
    )
    await service.store(
        context_key="project:app2",
        entry_type="instruction",
        content="Use MySQL database",
    )

    result = await service.search(query="database", context_key="project:app1")

    assert len(result.memories) == 1
    assert "PostgreSQL" in result.memories[0].content


@pytest.mark.asyncio
async def test_update_memory(service: MemoryService):
    stored = await service.store(
        context_key="global",
        entry_type="preference",
        content="Original content",
    )

    updated = await service.update(
        memory_id=stored.id,
        content="Updated content",
    )

    assert updated.id == stored.id
    assert updated.updated_at > stored.created_at

    memory = await service.get(stored.id)
    assert memory.content == "Updated content"


@pytest.mark.asyncio
async def test_update_memory_not_found(service: MemoryService):
    from snow.service import NotFoundError

    with pytest.raises(NotFoundError):
        await service.update(
            memory_id="non-existent-id",
            content="test",
        )


@pytest.mark.asyncio
async def test_soft_delete_memory(service: MemoryService):
    stored = await service.store(
        context_key="global",
        entry_type="preference",
        content="To be deleted",
    )

    result = await service.delete(memory_id=stored.id, permanent=False)

    assert result.deleted is True
    assert result.permanent is False

    result = await service.recall(context_key="global")
    assert len(result.memories) == 0


@pytest.mark.asyncio
async def test_hard_delete_memory(service: MemoryService):
    stored = await service.store(
        context_key="global",
        entry_type="preference",
        content="To be permanently deleted",
    )

    result = await service.delete(memory_id=stored.id, permanent=True)

    assert result.deleted is True
    assert result.permanent is True
