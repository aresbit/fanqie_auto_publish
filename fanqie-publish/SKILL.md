---
name: fanqie-publish
description: Automates publishing novel chapters to 番茄小说 (fanqienovel.com) via Playwright browser automation. Use when the user wants to publish, batch-upload, or retry uploading novel chapters from a local directory to 番茄小说. Handles login state, ProseMirror editor injection, popup dismissal (错别字检测/仅基础检测/AI声明/确认发布), and auto-archives successfully published files. Triggers on requests like "发布章节到番茄", "上传小说", "batch publish chapters", or retrying failed chapters.
---

# fanqie-publish

## Prerequisites

```bash
cd /home/ares/ares/llm/fanqie_auto_publish
uv sync                          # install deps
playwright install chromium      # first time only
```

Login (one-time, saves cookies to `state.json`):
```bash
DISPLAY=:0 uv run python login.py
# Follow on-screen prompt: log in, then press Enter
```

## Chapter File Naming

Files must live in `<SOURCE_DIR>/<书名>/` and be named:
```
001 第1章 章节标题.md
002 第2章 章节标题.md
```
Supports `.md` and `.txt`. `.md` files are auto-converted to plain text on publish.

## Batch Publish (primary method)

Edit the three constants at the top of `batch_publish.py`:

```python
CHAPTER_DIR = "/path/to/chapters/书名"
ARCHIVE_DIR = "/path/to/chapters/uploaded/书名"
BOOK_ID     = "7640498714590579774"   # from fanqienovel.com writer URL
```

Run:
```bash
DISPLAY=:0 uv run python batch_publish.py              # all chapters
DISPLAY=:0 uv run python batch_publish.py --count 5    # first 5 only
DISPLAY=:0 uv run python batch_publish.py --headless   # headless (less reliable)
```

Published files are moved to `ARCHIVE_DIR` automatically. Failed chapters stay in `CHAPTER_DIR`.

## Retrying Failed Chapters

Move files back from archive to source, then re-run:
```bash
mv /path/to/uploaded/书名/NNN*.md /path/to/chapters/书名/
DISPLAY=:0 uv run python batch_publish.py
```

## Getting BOOK_ID

Open the book in the writer backend. Extract the numeric ID from the URL:
```
https://fanqienovel.com/main/writer/7640498714590579774/manage/
```

## Known Failure Modes & Fixes

See `references/publish-flow.md` for the full browser automation flow, popup sequence, and known failure patterns.

## MCP Server (alternative)

`mcp_server.py` exposes `publish_chapters`, `list_books`, `preview_chapters`, `read_chapter_content`, and `check_login_status` as MCP tools. See `references/mcp-usage.md`.
