from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PreferenceMetadata(BaseModel):
    scope: Literal["global", "project"] = "global"
    priority: int = Field(default=0, ge=0, le=100)


class InstructionMetadata(BaseModel):
    applies_to: list[str] = Field(default_factory=list)
    auto_apply: bool = False


class SnippetMetadata(BaseModel):
    language: str | None = None
    tags: list[str] = Field(default_factory=list)


class ContextMetadata(BaseModel):
    source: str | None = None
    expires_at: datetime | None = None


METADATA_SCHEMAS: dict[str, type[BaseModel]] = {
    "preference": PreferenceMetadata,
    "instruction": InstructionMetadata,
    "snippet": SnippetMetadata,
    "context": ContextMetadata,
}


class Memory(BaseModel):
    id: str
    context_key: str
    entry_type: Literal["preference", "instruction", "snippet", "context"]
    content: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class StoreInput(BaseModel):
    context_key: str
    entry_type: str
    content: str
    metadata: dict[str, Any] | None = None


class RecallInput(BaseModel):
    context_key: str


class SearchInput(BaseModel):
    query: str
    context_key: str | None = None


class UpdateInput(BaseModel):
    id: str
    content: str | None = None
    metadata: dict[str, Any] | None = None


class DeleteInput(BaseModel):
    id: str
    permanent: bool = False


class MemoryListResult(BaseModel):
    memories: list[Memory]


class StoreResult(BaseModel):
    id: str
    created_at: datetime


class UpdateResult(BaseModel):
    id: str
    updated_at: datetime


class DeleteResult(BaseModel):
    id: str
    deleted: bool
    permanent: bool
