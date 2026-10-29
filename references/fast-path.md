# Fast Path — Desktop UA + curl + regex

> The fastest way to read a WeChat Official Account article. Zero dependencies, zero Chrome
> launches, 2–3 seconds per article.

## The insight

WeChat renders article bodies client-side (CSR). The common assumption is that you therefore
*must* drive a real browser to read an article. That is true for the WeChat in-app browser UA —
but **not** for a desktop browser UA.

A request carrying a desktop browser UA usually receives `#js_content` already server-rendered
as static HTML. Plain `curl` plus a regex extracts it directly.

Measured on 2026-10-25 across three consecutive articles: **2–3 seconds each, 0 Chrome launches,
5 000–7 000 characters of body**.

```bash
# The UA that matters — desktop, NOT WeChat in-app
curl -sL -m 30 \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15" \
  -H "Accept-Language: zh-CN,zh;q=0.9" \
  "https://mp.weixin.qq.com/s/<ID>" -o /tmp/wx.html
```

## Usage

```bash
python3 scripts/fetch_fast.py "https://mp.weixin.qq.com/s/<ID>"          # body to stdout
python3 scripts/fetch_fast.py "https://mp.weixin.qq.com/s/<ID>" --title   # title only
python3 scripts/fetch_fast.py "https://mp.weixin.qq.com/s/<ID>" --json    # JSON
python3 scripts/fetch_fast.py "https://mp.weixin.qq.com/s/<ID>" -o out.md # write Markdown
```

## When to fall back to the 4-tier chain

`fetch_fast.py` writes a `NOTE:` line to stderr in either case:

| Signal | Meaning |
|---|---|
| `body only N chars (CSR?)` | body under 200 characters → the page was not server-rendered |
| `captcha markers detected` | the page is a captcha wall |
| `ERROR: empty response` | curl returned nothing (timeout or network block) |

In all three cases, switch to `wechat_article.py` (the 4-tier chain).

## The extraction-boundary trap

**A greedy `.*` is wrong here.** The HTML after `#js_content` contains roughly 2.9 MB of WeChat
chrome — the "微信扫一扫 / 赞 / 在看 / 分享" bar, the QR-code block, the reward area. A greedy match
produces a "body" that ends with several hundred lines of UI garbage and makes the output useless
for summarisation.

Use a bounded match, in this order:

1. non-greedy up to `</div><script` (what `wechat_article.py` uses)
2. non-greedy up to `<div class="rich_media_tool`
3. greedy fallback (last resort)

Then strip the WeChat-specific UI selectors — `scripts/strategies/curl_cffi_fetch.py` keeps the
canonical list in `WX_CLEAN_SELECTORS`:

```
script, style, noscript,
#js_share_notice, #js_pc_qr_code, #js_toobar3,
.qr_code_pc, .reward_area, .rich_media_tool,
#js_tags_section, .weui_dialog
```

## Verifying the result

```bash
python3 scripts/fetch_fast.py "<URL>" --json | python3 -c "
import json,sys
d = json.load(sys.stdin)
print('title:', d['title'])
print('chars:', d['content_chars'], 'captcha:', d['captcha'])
print('tail :', repr(d['content'][-120:]))
"
```

A clean result ends with the article's actual last sentence and contains none of
`微信扫一扫` / `预览时标签不可点`.

## Related

- [wechat-anti-crawl.md](wechat-anti-crawl.md) — captcha signatures and meta extraction
- [pure-image-articles.md](pure-image-articles.md) — the one format no headless browser can read
