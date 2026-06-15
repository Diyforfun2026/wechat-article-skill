# WeChat Article Fetcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

A WeChat Official Account article fetcher with a 4-tier fallback strategy to handle anti-bot walls and CSR (Client-Side Rendering).

## Highlights

- **80% of articles complete in 1.5–3s** (curl_cffi impersonates the Chrome TLS JA3 fingerprint)
- **Chrome headless fallback**: captcha walls and CSR-empty body no longer a problem
- **Sogou repost search**: the last line of defense when a captcha wall blocks you
- **Zero external dependencies**: no reliance on jina.ai or any third-party API
- **Cross-platform**: pure Python scripts, work with Hermes Agent / OpenClaw / Claude Code / any CLI
- **Structured output**: Markdown or JSON, ready for programmatic processing

## Quick Start

```bash
# Install dependencies
pip install requests curl_cffi websocket-client

# Try fetching an article
python3 scripts/wechat_article.py "https://mp.weixin.qq.com/s/xxx"
```

## Fetching Strategy

```
URL → captcha detection
  ├─ Captcha → Chrome headless → still blocked → Sogou repost search
  └─ Clean   → meta extraction → CSR body empty → Chrome fallback
```

## Documentation

- [SKILL.md](SKILL.md) — Full usage docs (install, API, limitations, FAQ)
- [references/wechat-anti-crawl.md](references/wechat-anti-crawl.md) — Anti-crawl technical details and verified solutions

## License

MIT
