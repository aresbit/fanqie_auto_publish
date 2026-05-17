# fanqie-auto-publish

番茄小说自动发布工具，基于 Playwright 浏览器自动化，支持批量发布 `.md` / `.txt` 章节到番茄作家后台。

---

## 环境要求

- Python 3.10+
- Linux / macOS / Windows（Linux 需要 `DISPLAY` 环境变量指向 X11 显示）
- uv（推荐）或 pip

---

## 安装

```bash
git clone https://github.com/aresbit/fanqie_auto_publish.git
cd fanqie_auto_publish

# 安装依赖
uv sync
# 或: pip install -r requirements.txt

# 安装 Chromium
playwright install chromium
```

---

## 登录（首次，仅需一次）

```bash
DISPLAY=:0 uv run python login.py
```

浏览器弹出后在页面内完成登录，回到终端按回车。登录状态保存到 `state.json`（已加入 `.gitignore`）。

---

## 章节目录结构

```
chapters/
└── 书名/
    ├── 001 第1章 章节标题.md
    ├── 002 第2章 章节标题.md
    └── ...
uploaded/
└── 书名/          # 发布成功后自动归档到此
```

- 支持 `.md` 和 `.txt`，`.md` 发布时自动去除 Markdown 语法
- 文件名前缀数字决定发布顺序

---

## 批量发布（推荐）

编辑 `batch_publish.py` 顶部三个常量：

```python
CHAPTER_DIR = "/path/to/chapters/书名"
ARCHIVE_DIR = "/path/to/chapters/uploaded/书名"
BOOK_ID     = "7640498714590579774"   # 番茄后台 URL 中的数字 ID
```

运行：

```bash
DISPLAY=:0 uv run python batch_publish.py              # 发布全部
DISPLAY=:0 uv run python batch_publish.py --count 5    # 只发布前 5 章
DISPLAY=:0 uv run python batch_publish.py --headless   # 无头模式
```

发布成功的章节自动移入 `ARCHIVE_DIR`，失败的保留在 `CHAPTER_DIR` 可直接重跑。

---

## 获取 BOOK_ID

打开番茄作家后台，进入书籍管理页，从 URL 中提取数字 ID：

```
https://fanqienovel.com/main/writer/7640498714590579774/manage/
```

---

## 其他脚本

| 脚本 | 用途 |
|---|---|
| `login.py` | 获取登录 Cookie |
| `publish.py` | 交互式 CLI 发布（多书选择） |
| `main_webview.py` | GUI 窗口版本（pywebview） |
| `rename.py` | 章节文件批量重命名 |
| `deai_process.py` | 去 AI 味文本处理 |
| `add_text.py` | 封面图加书名文字（Pillow） |
| `mcp_server.py` | MCP 服务，供 AI Agent 调用 |

---

## MCP 集成

在 Claude Code 的 `.mcp.json` 中添加：

```json
{
  "mcpServers": {
    "fanqie-publish": {
      "command": "uv",
      "args": ["run", "python", "mcp_server.py"],
      "cwd": "/path/to/fanqie_auto_publish"
    }
  }
}
```

加载 `fanqie-publish` skill 后可通过对话直接触发发布流程。

---

## 免责声明

本项目仅供技术研究与个人自动化使用，请遵守番茄小说平台相关规则。
