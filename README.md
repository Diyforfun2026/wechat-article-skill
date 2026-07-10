# 微信公众号文章抓取工具 / WeChat Article Fetcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![微信文章](https://img.shields.io/badge/微信-公众号-green.svg)](#) [![Anti-Crawl](https://img.shields.io/badge/反爬-对抗-orange.svg)](#)

> 一个面向 AI Agent 的微信公众号文章抓取工具，自带**四层降级策略**，专门解决微信公众号反爬墙和前端 CSR 渲染导致的拿不到正文问题。
>
> A WeChat Official Account article fetcher with a 4-tier fallback strategy to handle anti-bot walls and CSR (Client-Side Rendering).

---

## ✨ 核心亮点 / Highlights

| 中文 | English |
|---|---|
| 🚀 **80% 文章 1.5–3 秒搞定**：用 `curl_cffi` 模拟 Chrome 的 TLS JA3 指纹，绕过最常见的反爬拦截 | 🚀 **80% of articles complete in 1.5–3s** — `curl_cffi` impersonates the Chrome TLS JA3 fingerprint |
| 🛡️ **Chrome 无头兜底**：遇到验证码墙或 CSR 渲染抽空正文，自动切换 headless Chrome | 🛡️ **Chrome headless fallback** — captcha walls and CSR-empty body are no longer a problem |
| 🔍 **搜狗中转兜底**：连 Chrome 都过不去时，自动找搜狗缓存的转载版 | 🔍 **Sogou repost search** — the last line of defense when a captcha wall blocks you |
| 📦 **零第三方依赖**：不靠 jina.ai 这类外部 API，本地纯 Python 全自研 | 📦 **Zero external dependencies** — no reliance on jina.ai or any third-party API |
| 🌐 **跨平台通用**：纯 Python 脚本，Hermes Agent / OpenClaw / Claude Code / 任意 CLI 都能调 | 🌐 **Cross-platform** — pure Python scripts work with Hermes Agent / OpenClaw / Claude Code / any CLI |
| 📑 **结构化输出**：返回 Markdown 或 JSON，可直接被 Agent 程序化处理 | 📑 **Structured output** — Markdown or JSON, ready for programmatic processing |

## 🚀 快速开始 / Quick Start

```bash
# 安装依赖 / Install dependencies
pip install requests curl_cffi websocket-client

# 抓一篇文章试试 / Try fetching an article
python3 scripts/wechat_article.py "https://mp.weixin.qq.com/s/xxx"
```

## 🧠 抓取策略 / Fetching Strategy

```
URL → 验证码检测
  ├─ 撞墙 → Chrome 无头 → 还不行 → 搜狗转载搜索
  └─ 干净 → meta 抽取 → CSR 正文空 → Chrome 兜底
```

```
URL → captcha detection
  ├─ Captcha → Chrome headless → still blocked → Sogou repost search
  └─ Clean   → meta extraction → CSR body empty → Chrome fallback
```

## 📚 文档 / Documentation

| 文档 | Doc |
|---|---|
| [SKILL.md](SKILL.md) — 完整使用文档（安装、API、限制、FAQ） | Full usage docs (install, API, limitations, FAQ) |
| [references/wechat-anti-crawl.md](references/wechat-anti-crawl.md) — 反爬技术细节与已验证的解决方案 | Anti-crawl technical details and verified solutions |

## 📄 许可证 / License

MIT — 中国用户随便用、随便改、随便商用，欢迎 PR。
MIT — free to use, modify, and ship. PRs welcome.
