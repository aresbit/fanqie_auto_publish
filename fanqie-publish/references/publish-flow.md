# 番茄小说 Publish Flow & Failure Modes

## Full Browser Automation Flow

For each chapter, `batch_publish.py` does:

1. **Navigate** to `https://fanqienovel.com/main/writer/{BOOK_ID}/publish/`
2. **Dismiss popups** — Escape key × 5, then click any visible: 知道了 / 跳过 / 完成 / 下一步 / 我知道了 / 确认 / 关闭 / 继续
3. **Dismiss side panels** — Click all "下一步" buttons at `y > 100` (side panels for other books), then 完成/我知道了/跳过/关闭
4. **Fill chapter number** — `input.first.fill(chapter_num)`
5. **Fill chapter title** — `get_by_placeholder("请输入标题").fill(title)`
6. **Inject content** into ProseMirror editor via `execCommand('insertText')` (see below)
7. **Click 下一步** — select the button at `y < 100` (top publish bar, not side panels)
8. **Confirmation loop** (30 × 1s iterations):
   - Check `发布成功` → done
   - Click `仅基础检测` if visible (content detection dialog, appears after 提交)
   - Click `否` for AI声明 dialog
   - Click `确认发布` / `立即发布` / `发布` → done
   - Click `提交` / `继续发布` / `我知道了` / `确认` for intermediate popups

## ProseMirror Content Injection

番茄小说 uses ProseMirror. Direct DOM `innerText =` assignment does NOT update internal state — "正文字数 0" results. The correct approach:

```python
page.evaluate("""([el, text]) => {
    el.focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);
    document.execCommand('insertText', false, text);
}""", [handle, text])
```

Fallback: `page.keyboard.type(text[:200])` to activate the editor, then `execCommand` for the rest.

## Popup Sequence (most chapters)

```
下一步 → 错别字检测弹窗 [提交] → 仅基础检测弹窗 [仅基础检测] → AI声明 [否] → [确认发布]
```

Some chapters skip straight to `确认发布`. The confirmation loop handles both.

## Known Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| `正文字数 0` after inject | `innerText =` used instead of `execCommand` | Use `execCommand('insertText')` |
| Wrong "下一步" clicked | Side panel for another book has `下一步` at y=279 | Select by `y < 100` |
| `仅基础检测` never clicked | Dialog appears AFTER `提交` inside loop | Must check `仅基础检测` inside the 30-iter loop |
| Timeout on `input.first.click()` | Guide overlay (`___reactour` img) blocks click | Dismiss all guide dialogs before filling fields |
| Chapter archived but not published | Script clicks `确认发布` but publish silently failed (draft state) | Check platform manually; move file back from archive and retry |
| `execCommand` headless clipboard fail | Headless Chromium doesn't read X11 clipboard | Use `execCommand`, not `xclip + Ctrl+V` |

## Night-Time Warning

Chapters published between 00:00–07:00 may be held for review until morning. The script warns and asks for confirmation.
