---
name: wechat-article
description: WeChat Official Account article fetcher with a 4-tier fallback strategy (captcha detection → meta extraction → Chrome headless → Sogou repost search). Supports Markdown/JSON output, handles CSR rendering and anti-bot walls.
version: 1.1.0
author: wechat-article-skill contributors
license: MIT
---

# WeChat Article Fetcher

A WeChat Official Account article fetcher that maximises content retrieval through a 4-tier fallback strategy. Specifically optimised for WeChat's CSR (Client-Side Rendering) and anti-bot walls.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Fetching Strategy (4 Tiers)](#fetching-strategy-4-tiers)
- [Usage](#usage)
- [Output Format](#output-format)
- [API (Python Library Mode)](#api-python-library-mode)
- [Dependencies & Compatibility](#dependencies--compatibility)
- [Known Limitations](#known-limitations)
- [FAQ](#faq)
- [Contributing](#contributing)

## Features

- **80% of articles complete in 1.5–3s** (curl_cffi impersonates the Chrome TLS JA3 fingerprint)
- **Automatic captcha-wall bypass** → Chrome headless first → on failure, Sogou repost search
- **CSR dynamic-rendered articles** → Chrome headless fallback fetches the post-SSR HTML (3–4 MB, with full body)
- **Structured Markdown output** (title / author / publish time / cover / body)
- **Curl-level speed + browser-level fallback** — best of both worlds
- **Cross AI Agent platform compatibility** — pure Python scripts, no framework lock-in (Hermes Agent / OpenClaw / Claude Code / any CLI)

## Installation

### Dependencies

| Dependency        | Version       | Purpose                                                  |
|-------------------|---------------|----------------------------------------------------------|
| Python            | 3.9+          | Runtime                                                  |
| `requests`        | any           | Fallback HTTP fetcher                                    |
| `curl_cffi`       | any           | Primary HTTP fetcher (impersonates TLS JA3 fingerprint)  |
| `websocket-client`| any           | Chrome DevTools Protocol (CDP) communication             |
| Google Chrome / Chromium | 148+ | **Optional** — only needed for captcha/CSR articles      |

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/Diyforfun2026/wechat-article-skill.git
cd wechat-article-skill

# 2. Install Python dependencies
pip install requests curl_cffi websocket-client

# 3. (Optional) Install Chrome
# Without Chrome, articles behind captcha or limited by CSR cannot be fully fetched.
# However, meta info (title / author / time / cover) is always available.
```

## Fetching Strategy (4 Tiers)

```
URL → captcha_check (must run before meta)
  ├─ Captcha → Chrome headless first
  │             └─ Still blocked → Sogou repost search
  └─ No captcha → meta extraction
       └─ CSR body empty (body < 200 chars) → Chrome headless fallback
            └─ Chrome also fails → meta retained, body empty
```

**Key insights**:
- WeChat article body is **CSR dynamic-rendered** → the `#js_content` you get from curl is often empty
- But **meta tags (`og:title`, `og:description`, `og:image`, `publish_time`) are always readable**
- For captcha-blocked articles → search Sogou for reposts with the same title, aggregated into `fallback_urls`
- Chrome headless fetches the full post-SSR HTML (3–4 MB) in **8–12s**

### Strategy Details

#### Tier 0: Captcha Detection (must run first)
- 7 signature matches: TCaptcha JS, `cap_appid`, "环境异常" (env abnormal), "请输入验证码" (enter captcha), "访问频繁" (frequent access), etc.
- **Why before meta**: captcha pages also have `og:title` (an unhelpful captcha-page title), which must be filtered out

#### Tier 1: Meta Extraction (always succeeds)
- Parse HTML meta tags: `og:title`, `og:description`, `og:image`, `og:article:author`, `og:article:published_time`
- Account name extracted from `<strong class="profile_meta_nickname">`
- **Never fails** — even when captcha and Chrome both fail, meta provides at least the title and summary

#### Tier 2: Curl Fetch (fastest)
- **Prefers `curl_cffi`**: impersonates Chrome 120's TLS JA3 fingerprint, bypasses most Cloudflare/WeChat anti-bot
- Falls back to `requests` (sufficient in many cases)
- 1.5–3s for non-captcha articles; body may be empty (CSR limitation)

#### Tier 3: Chrome Headless Fallback (heaviest but most accurate)
- Launches an independent Chrome instance (`--headless=new`) with a temporary `--user-data-dir` for isolation
- Navigates via Chrome DevTools Protocol (CDP), waits for render, retrieves DOM
- Use cases:
  - Captcha bypass (80%+ success rate)
  - CSR body fetching (when curl can't get `#js_content` content)
- Each call starts and cleans up — **no background processes left behind**
- 25s auto-kill timeout

#### Tier 4: Sogou Repost Search (last resort)
- When captcha wall is unbreakable, search Sogou WeChat Search by article title
- Returns a list of reposts with the same title (including `publisher`, `summary`, `publish_time`)
- **Limitation**: Sogou redirect links cannot be automatically resolved to `mp.weixin.qq.com` URLs (server-side encryption + anti-spider). The user must manually click the Sogou link to reach the original.

## Usage

### Fetch a Single Article

```bash
# Default mode (Chrome fallback auto-enabled)
python3 scripts/wechat_article.py "https://mp.weixin.qq.com/s/abc"

# Disable Chrome (curl_cffi + Sogou only, faster but no body)
python3 scripts/wechat_article.py --no-chrome "https://mp.weixin.qq.com/s/abc"

# Meta-only (fastest, for summary-only use cases)
python3 scripts/wechat_article.py --no-content "https://mp.weixin.qq.com/s/abc"
```

### JSON Output

```bash
python3 scripts/wechat_article.py --json "https://mp.weixin.qq.com/s/abc" | jq .
# Key fields: method (curl_cffi/chrome_headless), chrome_used (bool), content_chars
```

### Sogou Repost Search (bypass captcha)

```bash
python3 scripts/wechat_article.py --sogou "article title keywords"
# Output: list with Sogou redirect links (user must click to reach the original)
```

### Batch Processing

```bash
cat urls.txt | while read url; do
  python3 scripts/wechat_article.py "$url" > "out_$(date +%s).md"
done
```

## Output Format

```markdown
# Article Title

**Publish Time**: 2026-06-10
**Account**: Account Name
**Original Link**: https://mp.weixin.qq.com/s/abc
**Cover**: https://mmbiz.qpic.cn/...
**Method**: curl_cffi

---

> Article summary (og:description)

[Body in Markdown (may be empty when CSR-limited)]

## Possible Repost Links (Sogou)
- [Repost Title](https://weixin.sogou.com/link?url=...)
```

## API (Python Library Mode)

```python
from scripts.wechat_article import fetch_article

result = fetch_article(
    "https://mp.weixin.qq.com/s/abc",
    want_content=True,      # Fetch body?
    timeout=15,              # curl timeout (seconds)
    use_chrome=True,         # Enable Chrome fallback when body is empty
)

print(f"Success: {result.success}")
print(f"Method: {result.method}")
print(f"Title: {result.title}")
print(f"Account: {result.account}")
print(f"Publish Time: {result.publish_time}")
print(f"Body: {result.content_md[:200]}...")
```

## Dependencies & Compatibility

| Environment | Compatibility                                                  |
|-------------|----------------------------------------------------------------|
| macOS       | ✅ Fully supported (Chrome headless + curl_cffi)               |
| Linux       | ✅ Chromium/Chrome required to enable headless fallback        |
| Windows     | ⚠️ Theoretically works (untested)                              |
| Docker      | ⚠️ Needs `--no-sandbox` flag (built-in)                        |

### Fetching Path Latency

| Path                       | Latency  | Success Rate       | Notes                                  |
|----------------------------|----------|--------------------|----------------------------------------|
| `curl_cffi` (direct)       | 1.5–3s   | ~80% no-captcha    | Body may be CSR-empty                  |
| Chrome headless            | 8–12s    | >95%               | Includes launch + JS render            |
| Sogou repost search        | 1–2s     | ~80%               | Hit not guaranteed                     |

### Python Version Compatibility

| Feature                              | 3.9+ | 3.8                | <3.8 |
|--------------------------------------|------|--------------------|------|
| `from __future__ import annotations` | ✅   | ✅                 | ❌   |
| `dataclasses`                        | ✅   | `pip install dataclasses` | ❌ |
| `urllib.request`                     | ✅   | ✅                 | ✅   |
| `websocket-client`                   | ✅   | ✅                 | ✅   |

> **Python 3.9+ recommended**

## Known Limitations

| Scenario                              | Description                                                            | Workaround                                                       |
|---------------------------------------|------------------------------------------------------------------------|------------------------------------------------------------------|
| Captcha wall ("环境异常" / environment abnormal) | Meta is empty                                                          | Chrome bypass (80%+ pass) → on failure → Sogou repost            |
| CSR dynamic rendering                 | `curl` returns empty `js_content`                                      | Chrome headless fetches post-SSR HTML                             |
| Video / audio embeds                  | Turndown simplifies to `<video>`/`<audio>` tags                        | Markdown renderer must support them                               |
| Lazy-loaded large images              | `data-src` not resolved                                                | To be optimised                                                  |
| 24h view count limit                  | Old articles lack `publish_time` field                                 | Only `og:title`/`description` reliable                           |
| Sogou redirect links                  | Not `mp.weixin.qq.com` URLs                                            | User must click the link manually                                 |

## FAQ

### Q: Why not just use jina.ai / r.jina.ai?
jina.ai may be unreachable due to IPv6 routing issues in some networks. This tool has zero external service dependencies — fully self-hosted.

### Q: Do I need to log in to WeChat?
No. The current version doesn't implement login state. If login-gated article support is needed in the future, you can export cookies via Chrome to a `wechat.cookies` file to enable it.

### Q: Will Sogou search get my IP rate-limited?
Sogou has rate limiting. Recommend no more than 5 QPS, with at least 2s sleep between calls. The code already includes rate-limit detection (captcha / security verification / "访问过于频繁" / too-frequent access); on hit, it returns an empty result.

### Q: Can I run it without Chrome?
Yes. With the `--no-chrome` flag, articles behind captcha or limited by CSR cannot have their body fetched, but meta info (title, author, time, cover) is always available.

## Contributing

Issues and PRs are welcome! Areas worth focusing on:

- [ ] Lazy-loaded image handling (`data-src` → `src`)
- [ ] Table-to-Markdown conversion
- [ ] Docker image / pip package
- [ ] More anti-crawl strategy adapters
