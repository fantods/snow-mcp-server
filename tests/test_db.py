import pytest

from snow.db import Database


@pytest.mark.asyncio
async def test_database_connect(temp_db: Database):
    assert temp_db._conn is not None


@pytest.mark.asyncio
async def test_store_and_recall(temp_db: Database):
    memory = await temp_db.store(
        context_key="global",
        entry_type="preference",
        content="Test content",
        metadata={"scope": "global"},
    )

    assert memory.id is not None
    assert memory.context_key == "global"
    assert memory.content == "Test content"

    memories = await temp_db.recall("global")
    assert len(memories) == 1
    assert memories[0].id == memory.id


@pytest.mark.asyncio
async def test_search_fts(temp_db: Database):
    await temp_db.store(
        context_key="global",
        entry_type="instruction",
        content="Use Python for backend services",
        metadata={},
    )
    await temp_db.store(
        context_key="global",
        entry_type="instruction",
        content="Use TypeScript for frontend",
        metadata={},
    )

    memories = await temp_db.search("Python", None)
    assert len(memories) == 1
    assert "Python" in memories[0].content


@pytest.mark.asyncio
async def test_search_like(temp_db: Database):
    await temp_db.store(
        context_key="global",
        entry_type="preference",
        content="Use dark mode",
        metadata={},
    )

    memories = await temp_db.search("da", None)
    assert len(memories) == 1
    assert "dark" in memories[0].content


@pytest.mark.asyncio
async def test_update(temp_db: Database):
    memory = await temp_db.store(
        context_key="global",
        entry_type="preference",
        content="Original",
        metadata={},
    )

    updated = await temp_db.update(memory.id, content="Updated", metadata=None)
    assert updated is not None
    assert updated.content == "Updated"


@pytest.mark.asyncio
async def test_soft_delete(temp_db: Database):
    memory = await temp_db.store(
        context_key="global",
        entry_type="preference",
        content="To delete",
        metadata={},
    )

    deleted = await temp_db.soft_delete(memory.id)
    assert deleted is True

    memories = await temp_db.recall("global")
    assert len(memories) == 0


@pytest.mark.asyncio
async def test_hard_delete(temp_db: Database):
    memory = await temp_db.store(
        context_key="global",
        entry_type="preference",
        content="To delete permanently",
        metadata={},
    )

    deleted = await temp_db.hard_delete(memory.id)
    assert deleted is True

    result = await temp_db.get_by_id(memory.id)
    assert result is None


@pytest.mark.asyncio
async def test_context_isolation(temp_db: Database):
    await temp_db.store(
        context_key="project:app1",
        entry_type="instruction",
        content="App 1 instruction",
        metadata={},
    )
    await temp_db.store(
        context_key="project:app2",
        entry_type="instruction",
        content="App 2 instruction",
        metadata={},
    )

    memories1 = await temp_db.recall("project:app1")
    memories2 = await temp_db.recall("project:app2")

    assert len(memories1) == 1
    assert len(memories2) == 1
    assert memories1[0].content == "App 1 instruction"
    assert memories2[0].content == "App 2 instruction"
