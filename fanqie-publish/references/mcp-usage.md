# MCP Server Usage

`mcp_server.py` exposes the publish workflow as MCP tools via FastMCP.

## Install in Claude Code

Add to `.mcp.json`:
```json
{
  "mcpServers": {
    "fanqie-publish": {
      "command": "uv",
      "args": ["run", "python", "mcp_server.py"],
      "cwd": "/home/ares/ares/llm/fanqie_auto_publish"
    }
  }
}
```

## Tools

### `list_books`
Scan source dir and list books with pending chapter counts.
```
Args: source_dir (optional)
```

### `preview_chapters`
List chapter filenames for a book.
```
Args: book_name, limit=10, source_dir (optional)
```

### `read_chapter_content`
Read a chapter's plain text (auto-converts .md).
```
Args: book_name, chapter_index (1-based), source_dir (optional)
```

### `publish_chapters`
Launch Playwright and publish chapters to 番茄小说.
```
Args:
  book_name       (required)
  count           (optional) — number of chapters, default all
  headless        (optional) — default false
  source_dir      (optional)
  archive_dir     (optional)
Returns: summary string with success/fail counts
```

### `check_login_status`
Check if `state.json` exists and is valid.

### `set_config`
Update default `source_dir` / `archive_dir` in `config.json`.

## Typical Agent Workflow

```
1. list_books                          → see what's pending
2. check_login_status                  → ensure logged in
3. publish_chapters(book_name="大道言灵", count=10)
4. Report results to user
```

## Note on Reliability

`batch_publish.py` (direct CLI) is more reliable than the MCP server approach because it uses direct URL navigation (`/publish/`) rather than navigating the writer management UI. Prefer `batch_publish.py` for large batches.
