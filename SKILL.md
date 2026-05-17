# 番茄小说自动发布 Skill

## 概述

通过 MCP 工具 `fanqie-publish` 直接用 CLI 管理并发布番茄小说章节。
支持 `.txt` 和 `.md` 格式的章节文件，`.md` 文件会自动转换为纯文本后再发布。

## 前置条件

1. 已安装依赖：`uv sync` 或 `pip install fastmcp playwright`
2. 已安装 Chromium：`playwright install chromium`
3. 已登录获取 Cookie：运行 `uv run python login.py` 完成扫码登录

## MCP 工具清单

本 Skill 通过 MCP server `fanqie-publish` 暴露以下工具：

### 1. `list_books` — 列出所有待发书籍

扫描 `chapters/` 目录，列出所有有章节待发的书籍及章数。

```
Args:
  source_dir (可选): 章节源目录，默认用 config.json 中的配置

Returns:
  书籍列表，含待发章数
```

### 2. `preview_chapters` — 预览某书的待发章节

```
Args:
  book_name (必填): 书名
  limit (可选): 最多显示多少章，默认 10
  source_dir (可选)
```

### 3. `read_chapter_content` — 读取章节内容

读取指定书籍的第 N 章纯文本内容（.md 自动转换）。

```
Args:
  book_name (必填): 书名
  chapter_index (必填): 章节序号，从 1 开始
  source_dir (可选)
```

### 4. `publish_chapters` — 发布章节到番茄平台

自动打开浏览器，逐章发布。会自动处理弹窗、分卷、AI声明等。

```
Args:
  book_name (必填):  书名
  count (可选):       发布几章，None=全部
  volume (可选):      第几卷，None=不切换卷
  headless (可选):    是否无头模式，默认 false
  source_dir (可选)
  archive_dir (可选)

Returns:
  发布结果摘要
```

### 5. `check_login_status` — 检查登录状态

```
Returns:
  是否已登录
```

### 6. `set_config` — 配置目录

```
Args:
  source_dir (可选):  章节源目录
  archive_dir (可选): 归档目录
```

## Agent 使用指南

### 典型工作流

**Step 1 — 了解现状：**
```
先调用 list_books，了解有哪些书、各有多少章待发
```

**Step 2 — 确认内容（可选）：**
```
调用 preview_chapters 查看章节文件名
调用 read_chapter_content 抽查某章内容是否正确
```

**Step 3 — 检查登录：**
```
调用 check_login_status，确保已登录
如未登录 → 提示用户运行: uv run python login.py
```

**Step 4 — 执行发布：**
```
调用 publish_chapters(book_name="某书", count=5, volume=1)
```

**Step 5 — 报告结果：**
```
向用户汇报发布了多少章、归档到了哪里
```

### 注意事项

- **登录是前置条件**：`state.json` 不存在时 `publish_chapters` 会直接返回错误
- **分卷**：如果不传 `volume` 参数，番茄平台会保持上次选择的分卷
- **headless**：首次运行建议不设 `headless=True`，以便观察浏览器行为
- **.md 支持**：章节文件可以是 `.txt` 或 `.md`，`.md` 文件发布时自动去除 Markdown 语法
- **文件命名**：章节文件建议命名为 `001 第1章 标题.txt` 或 `001 第1章 标题.md`
- **归档**：发布成功的章节会自动移动到 `uploaded/<书名>/` 目录

### 快捷发布（一行命令）

Agent 可以直接通过 MCP 工具链完成全流程：

```
fanqie-publish: list_books
fanqie-publish: publish_chapters(book_name="青冥独行录", count=3)
```

用户无需打开 GUI，完全通过对话即可管理发布。
