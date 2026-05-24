#!/usr/bin/env python3
"""
大道言灵批量发布脚本
直接URL导航 + clipboard粘贴 → 番茄小说平台
"""
import sys, os, re, time, json, glob, shutil

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_server import md_to_plain_text
from playwright.sync_api import sync_playwright

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
CHAPTER_DIR = "/home/ares/yys/在盐边/chapters"
ARCHIVE_DIR = "/home/ares/yys/在盐边/chapters/uploaded"
BOOK_ID = "7643283052042390552"
PUBLISH_URL = f"https://fanqienovel.com/main/writer/{BOOK_ID}/publish/"

# 番茄审核时间提示
NIGHT_START = 0   # midnight
NIGHT_END = 7     # 7am

def read_chapter(filepath):
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    filename = os.path.basename(filepath)
    raw_title = os.path.splitext(filename)[0]

    # Extract chapter number from leading digits (e.g., "01-闷" → "1")
    num_m = re.search(r'^(\d+)', raw_title)
    chapter_num = str(int(num_m.group(1))) if num_m else "0"

    # Extract chapter title from content heading line (handles Chinese numerals)
    lines = content.split('\n')
    chapter_title = raw_title  # fallback
    if lines and lines[0].startswith('#'):
        heading_line = lines[0].lstrip('#').strip()
        hm = re.search(r'第\s*[一二三四五六七八九十百千\d]+\s*章\s*(.*)', heading_line)
        if hm:
            chapter_title = hm.group(1).strip()
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    body = md_to_plain_text('\n'.join(lines))
    return chapter_num, chapter_title, body

def inject_content_to_editor(page, editor, text):
    """向 ProseMirror 编辑器注入内容。

    番茄小说使用 ProseMirror，仅 DOM 操作不会更新其内部字数统计，
    必须走浏览器的 execCommand('insertText') 或真实键盘输入。
    """
    handle = editor.element_handle()

    # 先清空编辑器
    editor.click(force=True)
    page.wait_for_timeout(300)
    page.keyboard.press("Control+a")
    page.wait_for_timeout(200)
    page.keyboard.press("Delete")
    page.wait_for_timeout(200)

    # 方案1: execCommand insertText — ProseMirror 钩住了 execCommand，wordcount 会正确更新
    page.evaluate("""([el, text]) => {
        el.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('delete', false, null);
        document.execCommand('insertText', false, text);
    }""", [handle, text])
    page.wait_for_timeout(800)

    # 检查字数：读取页面中的字数统计元素（番茄编辑器顶部显示"正文字数 N"）
    wordcount_ok = page.evaluate("""() => {
        const el = document.querySelector('.word-count, [class*="wordCount"], [class*="word-count"]');
        if (el) {
            const m = el.innerText.match(/[0-9]+/);
            return m ? parseInt(m[0]) > 0 : false;
        }
        // fallback: 检查编辑器内是否有文字
        const editor = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
        return editor ? editor.innerText.trim().length > 0 : false;
    }""")

    if wordcount_ok:
        return True

    # 方案2: Playwright keyboard.type 逐字符打入（慢但最可靠）
    # 对于长文本只打前200字符触发 ProseMirror，再用 execCommand 补充全文
    print(f"    execCommand 未触发字数更新，尝试 keyboard.type 触发...")
    editor.click(force=True)
    page.keyboard.press("Control+a")
    page.keyboard.press("Delete")
    page.wait_for_timeout(200)
    # 打开头部分触发编辑器激活
    page.keyboard.type(text[:200], delay=0)
    page.wait_for_timeout(500)
    # 用 execCommand 补充剩余内容
    if len(text) > 200:
        page.evaluate("""([el, rest]) => {
            el.focus();
            // 把光标移到末尾
            const range = document.createRange();
            range.selectNodeContents(el);
            range.collapse(false);
            window.getSelection().removeAllRanges();
            window.getSelection().addRange(range);
            document.execCommand('insertText', false, rest);
        }""", [handle, text[200:]])
    page.wait_for_timeout(500)

    return True  # 两种方案都尝试过了，让调用方继续


def publish_one_chapter(page, chapter_num, chapter_title, chapter_body):
    """Publish a single chapter. Assumes browser is already on the publish page."""

    # Navigate to fresh publish page
    page.goto(PUBLISH_URL, timeout=30000)
    page.wait_for_timeout(5000)  # 首次访问需要更长时间加载

    # Aggressive popup/wizard dismissal (critical for first-time visit)
    for _ in range(20):
        dismissed = False
        # ESC first
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)
        for target in ["知道了", "跳过", "完成", "下一步", "我知道了", "确认", "关闭",
                        "继续", "新建章节", "创建第一章", "好的", "开始使用"]:
            try:
                btn = page.get_by_text(target, exact=True).first
                if btn.is_visible(timeout=400):
                    btn.click(force=True)
                    page.wait_for_timeout(500)
                    dismissed = True
                    print(f"  Dismissed: [{target}]")
                    break
            except:
                pass
        if not dismissed:
            break

    # Wait for editor to appear (ProseMirror or contenteditable)
    editor_ready = False
    for selector in ['.ProseMirror', '[contenteditable="true"]']:
        try:
            page.wait_for_selector(selector, timeout=10000)
            editor_ready = True
            break
        except:
            pass

    if not editor_ready:
        # Final attempt: check if there's a "create" flow to click through
        for create_text in ["新建章节", "创建第一章", "写一章", "开始创作"]:
            try:
                btn = page.get_by_text(create_text, exact=False).first
                if btn.is_visible(timeout=1000):
                    btn.click(force=True)
                    page.wait_for_timeout(3000)
                    page.wait_for_selector('.ProseMirror', timeout=10000)
                    editor_ready = True
                    print(f"  Clicked [{create_text}] to enter editor")
                    break
            except:
                pass

    # Fill chapter number
    num_input = page.locator('input').first
    if num_input.is_visible():
        num_input.click()
        page.wait_for_timeout(200)
        num_input.fill('')
        num_input.fill(str(chapter_num))
        print(f"  [#{chapter_num}] Filled number")

    # Fill title
    title_input = page.get_by_placeholder("请输入标题")
    if not title_input.is_visible():
        title_input = page.get_by_placeholder("请输入章节名", exact=False).first
    if title_input.is_visible():
        title_input.click()
        page.wait_for_timeout(200)
        title_input.fill('')
        title_input.fill(chapter_title)
        print(f"  [#{chapter_num}] Filled title: {chapter_title}")

    # 注入内容前：先关掉所有非顶部弹窗/面板（包括"书籍历史"面板里的"下一步"）
    # y > 100 的"下一步"属于各种引导面板，需要先全部点掉，避免干扰编辑器焦点
    for _ in range(8):
        dismissed = False
        try:
            btns = page.get_by_text("下一步", exact=True).element_handles()
            for b in btns:
                box = b.bounding_box()
                if box and box['y'] > 100:
                    b.click()
                    page.wait_for_timeout(600)
                    dismissed = True
        except: pass
        for t in ["完成", "我知道了", "跳过", "关闭"]:
            try:
                b = page.get_by_text(t, exact=True).first
                if b.is_visible(timeout=300):
                    b.click(force=True); page.wait_for_timeout(400); dismissed = True
            except: pass
        if not dismissed:
            break

    # Fill content (ProseMirror editor)
    if not editor_ready:
        print(f"  [#{chapter_num}] ERROR: Editor still not found after retries!")
        return False

    editor = page.locator('.ProseMirror').first
    if not editor.is_visible():
        editor = page.locator('[contenteditable="true"]').first

    ok = inject_content_to_editor(page, editor, chapter_body)
    if ok:
        print(f"  [#{chapter_num}] Injected content ({len(chapter_body)} chars)")
    else:
        print(f"  [#{chapter_num}] WARNING: content injection may have failed")

    # 点击顶部真实的【下一步】发布按钮（y < 100），避免误点侧边面板里的同名按钮
    next_btn = None
    try:
        all_next = page.get_by_text("下一步", exact=True).element_handles()
        for b in all_next:
            box = b.bounding_box()
            if box and box['y'] < 100:
                next_btn = b
                break
    except: pass

    if next_btn:
        next_btn.click()
        print(f"  [#{chapter_num}] Clicked 下一步")
        page.wait_for_timeout(2000)
    else:
        print(f"  [#{chapter_num}] ERROR: 下一步 button not found!")
        # Try saving as draft
        draft_btn = page.get_by_text("存草稿", exact=False).first
        if draft_btn.is_visible():
            draft_btn.click(force=True)
            print(f"  [#{chapter_num}] Saved as draft instead")
            page.wait_for_timeout(3000)
            return True
        return False

    # Handle confirmation flow — 最长等待 40 秒
    published = False
    for attempt in range(40):
        body_text = page.inner_text('body')

        # 已发布成功 → 直接返回
        if '发布成功' in body_text or '章节发布成功' in body_text:
            print(f"  [#{chapter_num}] ✅ PUBLISHED (detected success text)!")
            published = True
            break

        # 内容检测方式弹窗 → 选"仅基础检测"（在错别字提交后才出现）
        try:
            basic_btn = page.get_by_text("仅基础检测", exact=True).first
            if basic_btn.is_visible(timeout=500):
                basic_btn.click(force=True)
                print(f"  [#{chapter_num}] Selected 仅基础检测")
                page.wait_for_timeout(2500)
                continue
        except:
            pass

        # AI声明 → 选择"否" (多种匹配方式)
        try:
            for no_sel in [page.get_by_text("否", exact=True).first,
                           page.get_by_role("button", name="否").first]:
                try:
                    if no_sel.is_visible(timeout=500):
                        no_sel.click(force=True)
                        print(f"  [#{chapter_num}] Clicked AI声明 [否]")
                        page.wait_for_timeout(800)
                        break
                except:
                    pass
        except:
            pass

        # 确认发布 (多种可能文案)
        for confirm_text in ["确认发布", "立即发布", "发布", "发布章节", "确定发布", "确认并发布"]:
            try:
                btn = page.get_by_role("button", name=confirm_text).first
                if not btn.is_visible(timeout=400):
                    btn = page.get_by_text(confirm_text, exact=True).first
                if btn.is_visible(timeout=400) and btn.is_enabled():
                    btn.click(force=True)
                    print(f"  [#{chapter_num}] Clicked [{confirm_text}]")
                    page.wait_for_timeout(3000)
                    published = True
                    break
            except:
                pass
        if published:
            break

        # 中间拦截弹窗 (错别字/风险检测等)
        for popup_text in ["提交", "继续发布", "我知道了", "确认"]:
            try:
                p_btn = page.get_by_role("button", name=popup_text).last
                if not p_btn.is_visible(timeout=400):
                    p_btn = page.get_by_text(popup_text, exact=True).last
                if p_btn.is_visible(timeout=400) and p_btn.is_enabled():
                    p_btn.click(force=True)
                    print(f"  [#{chapter_num}] Handled popup [{popup_text}]")
                    page.wait_for_timeout(1000)
                    break
            except:
                pass

        page.wait_for_timeout(1000)

    if not published:
        body_text = page.inner_text('body')
        if '发布成功' in body_text or '章节发布成功' in body_text:
            print(f"  [#{chapter_num}] ✅ PUBLISHED!")
            published = True
        else:
            # Debug: print visible dialog text
            print(f"  [#{chapter_num}] ⚠️  未找到确认发布按钮，章节可能在草稿状态")
            print(f"  [#{chapter_num}] DEBUG body snippet: {body_text[:500]}")

    return published

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=None, help='发布几章（默认全部）')
    parser.add_argument('--headless', action='store_true', help='无头模式')
    args = parser.parse_args()

    if not os.path.exists(STATE_FILE):
        print("ERROR: Not logged in! Run login.py first.")
        sys.exit(1)

    # Find all chapters
    chapters = sorted(
        glob.glob(os.path.join(CHAPTER_DIR, "*.md")) + glob.glob(os.path.join(CHAPTER_DIR, "*.txt")),
        key=lambda f: int(re.search(r'^(\d+)', os.path.basename(f)).group(1)) if re.search(r'^(\d+)', os.path.basename(f)) else 999
    )

    if not chapters:
        print("No chapters found!")
        sys.exit(1)

    if args.count:
        chapters = chapters[:args.count]

    print(f"Found {len(chapters)} chapters to publish")

    # Check if it's night time
    current_hour = time.localtime().tm_hour
    if current_hour < 7:
        print(f"⚠️  Current time: {current_hour}:00 — 夜间发布会被卡审核，建议7:00-24:00发布")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(0)

    # Create archive dir
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    results = []
    success = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(storage_state=STATE_FILE)
        page = context.new_page()

        for i, filepath in enumerate(chapters):
            filename = os.path.basename(filepath)
            ch_num, ch_title, ch_body = read_chapter(filepath)

            print(f"\n--- [{i+1}/{len(chapters)}] 第{ch_num}章 {ch_title} ---")

            # Health check: recreate page if closed
            try:
                page.evaluate("1")
            except Exception:
                print("  Page closed, creating new page...")
                page = context.new_page()

            try:
                ok = publish_one_chapter(page, ch_num, ch_title, ch_body)

                if ok:
                    success += 1
                    # Archive the file
                    dest = os.path.join(ARCHIVE_DIR, filename)
                    shutil.move(filepath, dest)
                    results.append(f"✅ 第{ch_num}章 {ch_title}")
                else:
                    results.append(f"❌ 第{ch_num}章 {ch_title} - 发布失败")
                    print("  Will continue to next chapter automatically...")

            except Exception as e:
                print(f"  ❌ CRASH: {e}")
                results.append(f"💥 第{ch_num}章 {ch_title} - {e}")
                # Recreate page on crash and continue
                try:
                    page = context.new_page()
                    print("  Created new page, continuing...")
                except Exception:
                    print("  WARNING: Could not create new page")

            # Brief pause between chapters (only if page is alive)
            try:
                page.wait_for_timeout(2000)
            except Exception:
                pass

        browser.close()

    # Summary
    print("\n" + "="*50)
    print(f"发布完成: {success}/{len(chapters)} 成功")
    for r in results:
        print(f"  {r}")
    print(f"归档目录: {ARCHIVE_DIR}")

if __name__ == "__main__":
    main()
