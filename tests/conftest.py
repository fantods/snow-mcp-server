import asyncio
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from snow.db import Database
from snow.service import MemoryService


@pytest_asyncio.fixture
async def temp_db(tmp_path: Path) -> AsyncGenerator[Database, None]:
    db_path = tmp_path / "test.db"
    db = await Database.connect(db_path)
    yield db
    await db.close()


@pytest_asyncio.fixture
async def service(temp_db: Database) -> MemoryService:
    return MemoryService(temp_db)
