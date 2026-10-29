# Pure-Image Articles — the one format no browser can read

> Some WeChat Official Accounts publish the entire article as a set of long images. Headless
> Chrome can never read them. This file explains why, how to diagnose it in 2 seconds, and what
> to do instead.

## The five diagnostic signals

A pure-image article hits **all five**:

1. The `#js_content` element carries a `class="image_content"` attribute instead of the usual
   `rich_media_content`.
2. Inside `#js_content` there is only one `<h1 class="rich_media_title">` plus one
   `<p id="js_image_desc">` (containing `#hashtag` tags) — plus `<!-- -->` placeholders.
3. Even after CDP sets a 8000px viewport to trigger lazy loading,
   `document.querySelectorAll('#js_content img').length` is still **1** (the cover image).
4. The raw HTML contains 20–50 `mmbiz` image URLs in preload/link tags, but fetching them
   directly (with `Referer: https://mp.weixin.qq.com/`) returns **the cover image every time** —
   WeChat's anti-scraping falls back non-WeChat-browser content images to the cover.
5. The text portion of the article is 100–500 characters of topic tags; everything else is pixels.

## Why headless Chrome cannot help

This content is published in `#js_image_content` mode and depends on the **WeChat in-app browser
WebView** to render the long images. Headless Chrome is a plain WebKit/Blink build, not the WeChat
WebView, so the long-image lazy loading never triggers. The images are simply not there for a
non-WeChat client.

This is by design. Headless will never open it.

## 2-second diagnosis

```python
import re, subprocess

url = "https://mp.weixin.qq.com/s/<ID>"
html = subprocess.run(
    ["chrome", "--headless=new", "--dump-dom", url],
    capture_output=True, text=True,
).stdout

is_image_content = 'class="image_content"' in html
m = re.search(r'id="js_content"[^>]*>(.*?)<div class="rich_media_tool"', html, re.S)
content_size = len(m.group(1)) if m else 0

# Normal article: js_content is typically > 30 KB
# Image article: js_content is typically < 15 KB
if is_image_content and content_size < 15000:
    print("PURE IMAGE ARTICLE — headless cannot read this")
```

A single `grep` also works:

```bash
grep -o 'id="js_content"[^>]*' /tmp/wx_dump.html | head -1
# normal:  id="js_content" style="visibility: hidden;"
# images:  id="js_content" class="image_content"
```

## What to do instead

**Recommended: ask the user to save the images and send them back.** It is faster and more
reliable than any fallback chain.

1. Ask how many images there are **before** asking for them — so you know when the set is
   complete and don't summarise a half-batch.
2. Have the user long-press each image in the WeChat app to save it to their photo album, then send
   them straight into the conversation.
3. Read them straight from the message context when the platform renders them inline (no vision
   tool call needed). If you only have a local path, call the vision tool **one image at a time** —
   concurrent vision calls trigger a `DaemonThreadPoolExecutor` bug in some backends.
4. Archive the originals next to the summary, then write one structured summary across all pages.

Tried and measured: 9 images, 2 minutes, zero failures — versus 5 tool calls and ~3 minutes of
failure on the automated path.

## Anti-patterns — do not do these

| ❌ Don't | Why |
|---|---|
| Treat every `<img>` inside `#js_content` as content | The vision model will "complete" the missing content and hallucinate a plausible tutorial |
| Bulk-download the `mmbiz` URLs from the preload tags | They are all cover images or 243-byte placeholders |
| Tune Chrome flags (UA / viewport / virtual-time-budget) | The format is architecturally inaccessible outside the WeChat WebView |
| Summarise a tutorial you could not actually read | Fabricated content is worse than an honest "I can't read this" |

## Reporting back honestly

When you give up, say so plainly and offer options:

> ⚠️ This is a pure-image article (`#js_image_content` format) — WeChat's anti-scraping falls back
> to the cover image for every content image outside the WeChat browser, so headless Chrome cannot
> read it.
> - Account: [name]
> - Link: [url]
> - Readable: title + N #hashtag tags
> - The N images need the WeChat app on a phone.
>
> Want me to continue? (a) you paste the text (b) I retry via CDP (5 min) (c) skip

## Related

- [fast-path.md](fast-path.md) — the fast path that works for 95% of articles
- [wechat-anti-crawl.md](wechat-anti-crawl.md) — captcha signatures and meta extraction
