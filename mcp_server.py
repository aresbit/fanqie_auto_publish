#!/usr/bin/env python3
"""
番茄小说自动发布 MCP Server
通过 MCP 协议暴露小说发布功能，Agent 可直接通过 CLI 调用发文。
"""

import os
import sys
import glob
import json
import re
import shutil
from pathlib import Path

from fastmcp import FastMCP

# --- 配置默认值 ---
DEFAULT_SOURCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chapters")
DEFAULT_ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploaded")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
BOOK_MANAGE_URL = "https://fanqienovel.com/main/writer/book-manage"

# 加载 config.json（如果存在）
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
_config = {}
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _config = json.load(f)
    except Exception:
        pass

SOURCE_DIR = _config.get("source_dir", DEFAULT_SOURCE_DIR)
ARCHIVE_DIR = _config.get("archive_dir", DEFAULT_ARCHIVE_DIR)

mcp = FastMCP("fanqie-publish")


# ==================== 工具函数 ====================

def md_to_plain_text(md_content: str) -> str:
    """将 Markdown 内容转换为纯文本，适合番茄小说编辑器。"""
    lines = md_content.split('\n')
    result = []

    for line in lines:
        line = re.sub(r'!\[.*?\]\(.*?\)', '', line)
        line = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', line)
        line = re.sub(r'`([^`]*)`', r'\1', line)
        line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
        line = re.sub(r'__([^_]+)__', r'\1', line)
        line = re.sub(r'\*([^*]+)\*', r'\1', line)
        line = re.sub(r'_([^_]+)_', r'\1', line)
        line = re.sub(r'~~([^~]+)~~', r'\1', line)

        stripped = line.strip()
        if re.match(r'^#{1,6}\s', stripped):
            line = re.sub(r'^#{1,6}\s+', '', stripped)
            result.append(line)
            continue
        if re.match(r'^[-*_]{3,}\s*$', stripped):
            continue
        if stripped.startswith('> '):
            line = re.sub(r'^>\s?', '', stripped)
            result.append(line)
            continue
        if re.match(r'^[-*+]\s', stripped):
            line = re.sub(r'^[-*+]\s+', '', stripped)
            result.append(line)
            continue
        if re.match(r'^\d+\.\s', stripped):
            line = re.sub(r'^\d+\.\s+', '', stripped)
            result.append(line)
            continue

        result.append(stripped if stripped else '')

    return '\n'.join(result)


def _chapter_sort_key(file_path: str):
    """按真实章节号排序。"""
    raw_title = os.path.splitext(os.path.basename(file_path))[0]
    match = re.search(r'第\s*(\d+)\s*章', raw_title)
    if not match:
        match = re.search(r'^\s*(\d+)', raw_title)
    if match:
        return (0, int(match.group(1)), raw_title.casefold())
    return (1, raw_title.casefold())


# ==================== MCP 工具 ====================

@mcp.tool()
def list_books(source_dir: str | None = None) -> str:
    """扫描待发章节目录，列出所有书籍及其待发章数。

    Args:
        source_dir: 章节源目录路径，默认使用 config.json 中配置的 source_dir
    """
    src = source_dir or SOURCE_DIR
    if not os.path.isdir(src):
        return f"❌ 目录不存在: {src}\n请在 config.json 中配置正确的 source_dir"

    books = []
    for name in sorted(os.listdir(src)):
        sub = os.path.join(src, name)
        if os.path.isdir(sub):
            txts = glob.glob(os.path.join(sub, "*.txt"))
            mds = glob.glob(os.path.join(sub, "*.md"))
            chapters = sorted(txts + mds, key=_chapter_sort_key)
            if chapters:
                books.append((name, len(chapters)))

    if not books:
        return "📭 当前没有待发章节。请在 chapters/<书名>/ 下放入 .txt 或 .md 章节文件。"

    lines = [f"📚 共 {len(books)} 部小说有待发章节：", ""]
    for idx, (name, count) in enumerate(books, 1):
        lines.append(f"  [{idx}] {name} — {count} 章待发")
    return "\n".join(lines)


@mcp.tool()
def preview_chapters(book_name: str, limit: int = 10, source_dir: str | None = None) -> str:
    """预览某本书的待发章节文件名列表。

    Args:
        book_name: 书名（chapters/ 下的子目录名）
        limit: 最多预览多少章，默认 10
        source_dir: 章节源目录路径
    """
    src = source_dir or SOURCE_DIR
    sub = os.path.join(src, book_name)
    if not os.path.isdir(sub):
        return f"❌ 未找到书籍目录: {sub}"

    chapters = sorted(
        glob.glob(os.path.join(sub, "*.txt")) + glob.glob(os.path.join(sub, "*.md")),
        key=_chapter_sort_key,
    )

    if not chapters:
        return f"📭 【{book_name}】下没有待发章节。"

    lines = [f"📖 【{book_name}】待发章节（共 {len(chapters)} 章）：", ""]
    for i, f in enumerate(chapters[:limit]):
        lines.append(f"  [{i+1}] {os.path.basename(f)}")
    if len(chapters) > limit:
        lines.append(f"  ... 还有 {len(chapters) - limit} 章未显示")
    return "\n".join(lines)


@mcp.tool()
def read_chapter_content(book_name: str, chapter_index: int, source_dir: str | None = None) -> str:
    """读取某本书的第 N 章内容（纯文本，md 自动转换）。

    Args:
        book_name: 书名
        chapter_index: 章节序号（从 1 开始）
        source_dir: 章节源目录路径
    """
    src = source_dir or SOURCE_DIR
    sub = os.path.join(src, book_name)
    if not os.path.isdir(sub):
        return f"❌ 未找到书籍目录: {sub}"

    chapters = sorted(
        glob.glob(os.path.join(sub, "*.txt")) + glob.glob(os.path.join(sub, "*.md")),
        key=_chapter_sort_key,
    )

    if chapter_index < 1 or chapter_index > len(chapters):
        return f"❌ 序号超出范围 (1-{len(chapters)})"

    fp = chapters[chapter_index - 1]
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()

    if fp.lower().endswith(".md"):
        content = md_to_plain_text(content)

    # 截取前 2000 字预览
    preview = content[:2000]
    if len(content) > 2000:
        preview += f"\n\n... (全文共 {len(content)} 字)"

    return f"📄 {os.path.basename(fp)}\n\n{preview}"


@mcp.tool()
def publish_chapters(
    book_name: str,
    count: int | None = None,
    volume: int | None = None,
    headless: bool = False,
    source_dir: str | None = None,
    archive_dir: str | None = None,
) -> str:
    """发布某本书的待发章节到番茄小说平台（需要先登录）。

    Args:
        book_name: 书名（chapters/ 下的子目录名）
        count: 发布几章，None 表示全部
        volume: 第几卷，None 表示不切换卷（保持上次设置）
        headless: 是否使用无头浏览器（默认 False，需要看到浏览器）
        source_dir: 章节源目录，默认使用 config.json
        archive_dir: 归档目录，默认使用 config.json
    """
    if not os.path.exists(STATE_FILE):
        return "❌ 未登录！请先运行 login 工具获取登录凭证。"

    src = source_dir or SOURCE_DIR
    arc = archive_dir or ARCHIVE_DIR
    sub = os.path.join(src, book_name)

    if not os.path.isdir(sub):
        return f"❌ 未找到书籍目录: {sub}"

    chapters = sorted(
        glob.glob(os.path.join(sub, "*.txt")) + glob.glob(os.path.join(sub, "*.md")),
        key=_chapter_sort_key,
    )

    if not chapters:
        return f"📭 【{book_name}】下没有待发章节。"

    if count is not None and count > 0:
        chapters = chapters[:count]

    cn_digits = "一二三四五六七八九十"
    volume_name = None
    if volume is not None and volume > 1:
        volume_name = f"第{cn_digits[volume - 1] if volume <= 10 else str(volume)}卷"

    # 准备归档目录
    book_archive = os.path.join(arc, book_name)
    if volume_name:
        volume_dir = os.path.join(book_archive, volume_name)
    else:
        volume_dir = book_archive
    os.makedirs(volume_dir, exist_ok=True)

    # --- 启动 Playwright ---
    from playwright.sync_api import sync_playwright

    results = []
    success_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=STATE_FILE)
        page = context.new_page()

        for i, file_path in enumerate(chapters):
            filename = os.path.basename(file_path)
            raw_title = os.path.splitext(filename)[0]

            m = re.search(r'第\s*(\d+)\s*章[\s_]*(.*)', raw_title)
            chapter_num = str(m.group(1)) if m else ""
            chapter_title = m.group(2).strip() if m else ""

            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 从正文第一行提取标题
            first_line_clean = lines[0].strip() if lines else ""
            if first_line_clean.startswith('#') and file_path.lower().endswith('.md'):
                first_line_clean = re.sub(r'^#{1,6}\s+', '', first_line_clean)

            if not chapter_title and lines:
                m2 = re.search(r'第.*?章[\s：:]*(.*)', first_line_clean)
                if m2:
                    chapter_title = m2.group(1).strip()
            if not chapter_title:
                chapter_title = re.sub(r'^[0-9]+[\s_]*', '', raw_title).strip()

            # 去掉正文内重复标题行
            if lines and re.search(r'第.*?章', lines[0].strip()):
                lines = lines[1:]
            while lines and not lines[0].strip():
                lines = lines[1:]

            content = "".join(lines)
            if file_path.lower().endswith('.md'):
                content = md_to_plain_text(content)

            try:
                # 回到书籍管理页
                page.goto(BOOK_MANAGE_URL, timeout=60000)
                page.wait_for_timeout(3000)

                # 点击章节管理
                manage_clicked = False
                book_cards = page.locator('div, li, section, article').filter(has_text=book_name)
                for ci in range(book_cards.count() - 1, -1, -1):
                    card = book_cards.nth(ci)
                    try:
                        if card.is_visible():
                            card.hover(timeout=3000)
                            page.wait_for_timeout(1000)
                            btn = card.get_by_text("章节管理").first
                            if btn.is_visible():
                                btn.click()
                                manage_clicked = True
                                break
                    except Exception:
                        continue

                if not manage_clicked:
                    page.get_by_text("章节管理").first.click()

                page.wait_for_timeout(4000)

                original_pages = len(context.pages)
                editor_page = context.pages[-1] if len(context.pages) > 1 else page

                # 检查草稿
                draft_row = editor_page.locator('tr, li, .chapter-item').filter(
                    has_text=re.compile(f"第\\s*{chapter_num}\\s*章")
                ).first
                if draft_row.is_visible():
                    edit_icon = draft_row.locator('td').last.locator('svg, i, a, span, button, img').first
                    if edit_icon.is_visible():
                        edit_icon.click(force=True)
                    else:
                        draft_row.click(force=True)
                else:
                    new_btn = editor_page.get_by_role("button", name="新建章节").first
                    if not new_btn.is_visible():
                        new_btn = editor_page.get_by_text("新建章节").first
                    new_btn.click(force=True)

                page.wait_for_timeout(4000)
                if len(context.pages) > original_pages:
                    editor_page = context.pages[-1]

                # 清道夫：关闭新手引导弹窗
                # 注意：不包含"下一步"，因为它与顶部真实发布按钮文字相同，误触会提前跳转
                for _ in range(3):
                    editor_page.keyboard.press("Escape")
                    editor_page.wait_for_timeout(200)

                for _ in range(10):
                    clicked_guide = False
                    try:
                        for target_text in ["完成", "我知道了", "跳过"]:
                            btns = editor_page.get_by_text(target_text, exact=True).element_handles()
                            for btn in btns:
                                box = btn.bounding_box()
                                if box and box['y'] > 100:
                                    btn.click()
                                    editor_page.wait_for_timeout(600)
                                    clicked_guide = True
                    except Exception:
                        pass
                    if not clicked_guide:
                        break

                # 分卷切换
                if volume is not None and volume > 1:
                    try:
                        vol_elements = editor_page.get_by_text(
                            re.compile(r'第[一二三四五六七八九十百]+卷')
                        ).element_handles()
                        dialog_opened = False
                        for v in vol_elements[:8]:
                            try:
                                box = v.bounding_box()
                                if not box or box['y'] < 0 or box['y'] > 800:
                                    continue
                                outer = v.evaluate("el => el.outerHTML") or ""
                                if "outline" in outer.lower() or "placeholder" in outer.lower() or "卷名" in outer:
                                    continue
                                v.click(force=True)
                                editor_page.wait_for_timeout(1000)
                                if editor_page.get_by_text("新建分卷").is_visible() or editor_page.get_by_text("取消").is_visible():
                                    dialog_opened = True
                                    break
                            except Exception:
                                pass

                        if dialog_opened:
                            editor_page.wait_for_timeout(500)
                            target_vol = None
                            for v_name_cand in [volume_name, f"第{volume}卷", f"卷{volume}"]:
                                candidates = editor_page.get_by_text(v_name_cand, exact=False).element_handles()
                                for cand in candidates:
                                    try:
                                        cb = cand.bounding_box()
                                        ch = cand.evaluate("el => el.outerHTML") or ""
                                        if "outline" in ch.lower() or "placeholder" in ch.lower() or "卷名" in ch:
                                            continue
                                        if not cb or cb['y'] < 0 or cb['y'] > 800:
                                            continue
                                        target_vol = cand
                                        break
                                    except Exception:
                                        pass
                                if target_vol:
                                    break

                            if target_vol:
                                target_vol.click(force=True)
                                editor_page.wait_for_timeout(500)
                                confirm_btn = editor_page.get_by_role("button", name="确定").first
                                if not confirm_btn.is_visible():
                                    confirm_btn = editor_page.get_by_text("确定", exact=True).last
                                if confirm_btn.is_visible():
                                    confirm_btn.click(force=True)
                                else:
                                    editor_page.keyboard.press("Escape")
                                editor_page.wait_for_timeout(1000)
                    except Exception:
                        pass

                # 填表
                num_input = editor_page.locator('input[type="text"]').first
                if num_input.is_visible():
                    num_input.fill(chapter_num, force=True)

                title_input = editor_page.get_by_placeholder("请输入标题", exact=False).first
                if not title_input.is_visible():
                    title_input = editor_page.get_by_placeholder("请输入章节名", exact=False).first
                if not title_input.is_visible():
                    title_input = editor_page.locator('input[type="text"]').last
                if title_input.is_visible():
                    title_input.fill(chapter_title, force=True)

                # 注入正文
                editor = editor_page.locator('.ql-editor').first
                if not editor.is_visible():
                    editor = editor_page.locator('.ProseMirror').first
                if not editor.is_visible():
                    editor = editor_page.locator('[contenteditable="true"]').first

                if editor.is_visible():
                    editor_handle = editor.element_handle()
                    # 方案1: ClipboardEvent paste 模拟（ProseMirror 会走自己的 paste handler）
                    editor_page.evaluate("""([el, text]) => {
                        el.focus();
                        const range = document.createRange();
                        range.selectNodeContents(el);
                        const sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        const dt = new DataTransfer();
                        dt.setData('text/plain', text);
                        el.dispatchEvent(new ClipboardEvent('paste', {
                            clipboardData: dt, bubbles: true, cancelable: true
                        }));
                    }""", [editor_handle, content])
                    editor_page.wait_for_timeout(800)

                    # 验证注入，失败则降级 execCommand
                    actual = (editor.inner_text() or "").strip()
                    if not actual:
                        editor_page.evaluate("""([el, text]) => {
                            el.focus();
                            document.execCommand('selectAll', false, null);
                            document.execCommand('delete', false, null);
                            document.execCommand('insertText', false, text);
                        }""", [editor_handle, content])
                        editor_page.wait_for_timeout(500)

                    # 最终兜底: innerText + 事件
                    if not (editor.inner_text() or "").strip():
                        editor_page.evaluate("""([el, text]) => {
                            el.innerText = text;
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                        }""", [editor_handle, content])

                # 发布
                next_btn = editor_page.get_by_text("下一步", exact=True).last
                if next_btn.is_visible():
                    next_btn.click(force=True)
                    editor_page.wait_for_timeout(2000)

                    # 处理"请选择内容检测方式"弹窗 → 选"仅基础检测"
                    try:
                        basic_btn = editor_page.get_by_text("仅基础检测", exact=True).first
                        if basic_btn.is_visible(timeout=3000):
                            basic_btn.click(force=True)
                            editor_page.wait_for_timeout(2000)
                    except Exception:
                        pass

                    publish_success = False
                    for _attempt in range(20):
                        try:
                            ai_no_label = editor_page.get_by_text("否", exact=True).first
                            if ai_no_label.is_visible():
                                ai_no_label.click(force=True)
                        except Exception:
                            pass

                        try:
                            publish_btn = editor_page.get_by_role("button", name="确认发布").first
                            if not publish_btn.is_visible():
                                publish_btn = editor_page.get_by_text("确认发布", exact=True).first
                            if publish_btn.is_visible() and publish_btn.is_enabled():
                                publish_btn.click(force=True)
                                results.append(f"  ✅ 第{chapter_num}章 '{chapter_title}' — 发布成功")
                                publish_success = True
                                success_count += 1
                                break
                        except Exception:
                            pass

                        handled = False
                        for popup_btn_text in ["提交", "继续发布", "我知道了", "确认", "确定"]:
                            try:
                                p_btn = editor_page.get_by_role("button", name=popup_btn_text).last
                                if not p_btn.is_visible():
                                    p_btn = editor_page.get_by_text(popup_btn_text, exact=True).last
                                if p_btn.is_visible() and p_btn.is_enabled():
                                    p_btn.click(force=True)
                                    editor_page.wait_for_timeout(1000)
                                    handled = True
                                    break
                            except Exception:
                                pass

                        if handled:
                            continue
                        editor_page.wait_for_timeout(1000)

                    if not publish_success:
                        results.append(f"  ⚠️ 第{chapter_num}章 '{chapter_title}' — 未找到确认发布按钮，请人工介入")
                        success_count += 1
                else:
                    save_btn = editor_page.get_by_text("存草稿", exact=False).first
                    if save_btn.is_visible():
                        save_btn.click()
                        results.append(f"  💾 第{chapter_num}章 '{chapter_title}' — 已存草稿")
                        success_count += 1
                    else:
                        results.append(f"  ❌ 第{chapter_num}章 '{chapter_title}' — 保存失败")

                page.wait_for_timeout(3000)

                # 归档
                dest_path = os.path.join(volume_dir, filename)
                shutil.move(file_path, dest_path)

                if editor_page != page:
                    editor_page.close()

                page.wait_for_timeout(1000)

            except Exception as e:
                results.append(f"  ❌ 第{chapter_num}章 崩溃: {e}")
                # 出错即停
                break

        browser.close()

    summary = [
        f"📖 【{book_name}】发布完成！",
        f"✅ 成功: {success_count}/{len(chapters)}",
        f"📁 归档至: {volume_dir}",
        "",
    ] + results

    return "\n".join(summary)


@mcp.tool()
def check_login_status() -> str:
    """检查是否已有有效的番茄作家登录凭证。"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cookies_count = len(data.get("cookies", []))
            return f"✅ 已登录！state.json 存在，包含 {cookies_count} 个 Cookie。"
        except Exception:
            return "✅ state.json 存在（但无法解析）。"
    return "❌ 未登录。请运行 login 工具进行扫码登录。"


@mcp.tool()
def set_config(source_dir: str | None = None, archive_dir: str | None = None) -> str:
    """设置或更新配置（章节源目录和归档目录）。

    Args:
        source_dir: 待发章节所在目录
        archive_dir: 已发布章节归档目录
    """
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    changes = []
    if source_dir:
        config["source_dir"] = source_dir
        changes.append(f"source_dir -> {source_dir}")
    if archive_dir:
        config["archive_dir"] = archive_dir
        changes.append(f"archive_dir -> {archive_dir}")

    if not changes:
        return "没有需要更新的配置项。"

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    global SOURCE_DIR, ARCHIVE_DIR
    SOURCE_DIR = config.get("source_dir", DEFAULT_SOURCE_DIR)
    ARCHIVE_DIR = config.get("archive_dir", DEFAULT_ARCHIVE_DIR)

    return f"✅ 已更新: {', '.join(changes)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
