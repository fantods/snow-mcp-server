# Snow MCP Server

Snow is a Model Context Protocol (MCP) server that provides AI agents with a persistent, contextual "brain." By bridging stateless AI reasoning with local filesystem persistence, Snow allows your AI agent to store and recall architectural preferences, project-specific snippets, and frequent instructions in a local SQLite database.

Unlike standard LLM sessions that reset context every time the process exits, Snow creates a long-term memory (LTM) layer. This ensures that established project preferences and instructions are automatically inherited by the AI in all future sessions, across any directory on your machine.

## Features

- **Contextual Recall**: Automatically provides relevant memories based on your current project (`project:name`) or global preferences (`global`)
- **Persistent Storage**: Uses SQLite with WAL (Write-Ahead Logging) mode for high-concurrency and reliability
- **XDG Compliant**: Stores data in `~/.local/share/snow/snow.db`
- **FTS5 Search**: Full-text search with fallback to LIKE for short queries
- **Typed Metadata**: Each entry type has its own validated metadata schema
- **Soft Delete**: Memories can be soft-deleted and optionally permanently removed

## Installation

```bash
# Clone or download this repository
git clone <repo-url>
cd snow-mcp-server

# Install dependencies
make install
```

## Client Integration

### OpenCode

Add Snow to your OpenCode configuration (`~/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "snow": {
      "type": "local",
      "command": ["uv", "run", "--directory", "/path/to/snow-mcp-server", "python", "-m", "snow.server"],
      "enabled": true
    }
  }
}
```

### Claude Code

Add Snow to your Claude Code configuration (`~/.config/claude-code/config.json`):

```json
{
  "mcpServers": {
    "snow": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/snow-mcp-server", "python", "-m", "snow.server"]
    }
  }
}
```

### Cursor

Add Snow to your Cursor configuration. Open Cursor Settings → Features → Model Context Protocol and add:

```json
{
  "mcpServers": {
    "snow": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/snow-mcp-server", "python", "-m", "snow.server"]
    }
  }
}
```

Or add directly to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "snow": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/snow-mcp-server", "python", "-m", "snow.server"]
    }
  }
}
```

Replace `/path/to/snow-mcp-server` with the actual path to this repository in all configurations above.

## Usage

### Tools

Snow provides 5 MCP tools:

#### `store_memory`

Store a new memory in the database.

```json
{
  "context_key": "project:myapp",
  "entry_type": "preference",
  "content": "Use 4-space indentation for Python files",
  "metadata": {
    "scope": "project",
    "priority": 10
  }
}
```

**Parameters:**
- `context_key` (required): Memory context - `global` or `project:<name>`
- `entry_type` (required): Type of memory - `preference`, `instruction`, `snippet`, or `context`
- `content` (required): The memory content (max 8KB)
- `metadata` (optional): Typed metadata based on entry_type

#### `recall_memory`

Recall all memories for a specific context.

```json
{
  "context_key": "project:myapp"
}
```

**Parameters:**
- `context_key` (required): Memory context to recall from

#### `search_memories`

Search memories by content.

```json
{
  "query": "TypeScript",
  "context_key": null
}
```

**Parameters:**
- `query` (required): Search query (uses FTS5 for 3+ chars, LIKE for shorter)
- `context_key` (optional): Filter to specific context

#### `update_memory`

Update an existing memory.

```json
{
  "id": "uuid-of-memory",
  "content": "Updated content",
  "metadata": null
}
```

**Parameters:**
- `id` (required): UUID of the memory to update
- `content` (optional): New content (max 8KB)
- `metadata` (optional): New metadata (validated against entry_type schema)

#### `delete_memory`

Delete a memory (soft delete by default).

```json
{
  "id": "uuid-of-memory",
  "permanent": false
}
```

**Parameters:**
- `id` (required): UUID of the memory to delete
- `permanent` (optional): If `true`, permanently remove from database (default: `false`)

## Entry Types & Metadata

Each entry type has its own validated metadata schema:

### `preference`
```json
{
  "scope": "global",     // "global" or "project"
  "priority": 0          // 0-100
}
```

### `instruction`
```json
{
  "applies_to": ["*.py", "*.ts"],  // File patterns
  "auto_apply": false              // Auto-apply flag
}
```

### `snippet`
```json
{
  "language": "python",     // Programming language
  "tags": ["utility", "io"] // Tags for categorization
}
```

### `context`
```json
{
  "source": "docs/api.md",              // Source reference
  "expires_at": "2025-12-31T00:00:00Z"  // Optional expiration
}
```

## Architecture

```
Client (AI Agent)
       |
       v
+------------------+
|  MCP Transport   |  (STDIO via FastMCP)
+------------------+
       |
       v
+------------------+
| MemoryService    |  (Validation, Business Logic)
+------------------+
       |
       v
+------------------+
|    Database      |  (SQLite + FTS5 + WAL)
+------------------+
       |
       v
~/.local/share/snow/snow.db
```

## Development

```bash
# Run in development mode with MCP Inspector
make dev

# Run tests
make test

# Run server directly
make run
```

## Database Schema

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    context_key TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP DEFAULT NULL
);

CREATE INDEX idx_context_relevance 
    ON memories(context_key, updated_at DESC);

CREATE VIRTUAL TABLE memories_fts USING fts5(
    content,
    content='memories',
    content_rowid='rowid'
);
```

## License

MIT
