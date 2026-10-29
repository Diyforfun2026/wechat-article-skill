# 微信公众号文章抓取工具 / WeChat Article Fetcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![微信文章](https://img.shields.io/badge/微信-公众号-green.svg)](#) [![Anti-Crawl](https://img.shields.io/badge/反爬-对抗-orange.svg)](#)
[![Topics](https://img.shields.io/badge/topics-wechat%20%7C%20mp--weixin%20%7C%20anti--crawl%20%7C%20scraper-blueviolet.svg)](https://github.com/topics/wechat-article)

> 一个面向 AI Agent 的微信公众号文章抓取工具，**两条抓取路径**（快路径 + 四层降级链），专门解决微信公众号反爬墙和前端 CSR 渲染导致的拿不到正文问题。
>
> A WeChat Official Account article fetcher with **two fetching paths** (fast path + 4-tier fallback) to handle anti-bot walls and CSR (Client-Side Rendering).

---

## ✨ 核心亮点 / Highlights

| 中文 | English |
|---|---|
| ⚡ **快路径 2–3 秒出正文**：桌面浏览器 UA + curl + 正则，**零依赖、零 Chrome 启动** | ⚡ **Fast path: full body in 2–3s** — desktop UA + curl + regex, no dependencies, no Chrome launch |
| 🚀 **四层降级链兜底**：快路径失败时自动走 `curl_cffi → Chrome headless → Sogou 转载` | 🚀 **4-tier fallback chain** — `curl_cffi → Chrome headless → Sogou repost` when the fast path fails |
| 🛡️ **验证码墙检测**：7 种特征识别，验证码页先于 meta 判定（验证码页也有 `og:title`，是陷阱） | 🛡️ **Captcha detection** — 7 signatures, checked *before* meta (captcha pages also carry a bogus `og:title`) |
| 📦 **零第三方 API 依赖**：不靠 jina.ai 等外部服务，纯 Python 本地跑 | 📦 **No external API dependency** — no jina.ai, no third-party service, pure local Python |
| 🌐 **跨平台通用**：纯 Python 脚本，Hermes Agent / OpenClaw / Claude Code / 任意 CLI 都能调 | 🌐 **Cross-platform** — pure Python scripts work with Hermes Agent / OpenClaw / Claude Code / any CLI |
| 📑 **结构化输出**：Markdown 或 JSON，可直接被 Agent 程序化处理 | 📑 **Structured output** — Markdown or JSON, ready for programmatic processing |
| 🧩 **两种输出形态**：正文纯文本/Markdown，或带标题、作者、发布时间、封面的完整档案 | 🧩 **Two output shapes** — plain body text, or a full record with title / author / publish time / cover |

---

## 🚀 快速开始 / Quick Start

### 方式 A：快路径（推荐，零依赖）/ Fast path (recommended, zero deps)

```bash
# 抓一篇试试 / Try fetching an article
python3 scripts/fetch_fast.py "https://mp.weixin.qq.com/s/xxx"

# 只看标题 / Title only
python3 scripts/fetch_fast.py "https://mp.weixin.qq.com/s/xxx" --title

# JSON 输出（正文在 content 字段）/ JSON output
python3 scripts/fetch_fast.py "https://mp.weixin.qq.com/s/xxx" --json

# 存成 Markdown 文件 / Write to a Markdown file
python3 scripts/fetch_fast.py "https://mp.weixin.qq.com/s/xxx" -o article.md
```

**为什么快**：微信文章正文虽然是 CSR 渲染的，但用**桌面浏览器 UA** 请求时，`#js_content` 常常已经是服务端渲染好的静态 HTML。用普通 `curl` + 正则就能直接抽出来 —— 不需要 `curl_cffi`，也不需要启动 Chrome（省 8–12 秒和 150MB 内存）。

**关键点**：UA 必须用桌面浏览器，**不要用微信内置浏览器 UA**，否则大概率拿到 CSR 空正文。

### 方式 B：四层降级链（需要反爬对抗时）/ 4-tier fallback (when facing anti-bot)

```bash
# 安装依赖 / Install dependencies
pip install requests curl_cffi websocket-client

# 抓取（默认启用 Chrome 兜底）/ Fetch (Chrome fallback on by default)
python3 scripts/wechat_article.py "https://mp.weixin.qq.com/s/xxx"

# 禁用 Chrome（更快但无正文）/ Disable Chrome (faster, no body)
python3 scripts/wechat_article.py --no-chrome "https://mp.weixin.qq.com/s/xxx"

# 只拿 meta / Meta only
python3 scripts/wechat_article.py --no-content "https://mp.weixin.qq.com/s/xxx"

# 搜狗找转载 / Search Sogou for reposts
python3 scripts/wechat_article.py --sogou "article title keywords"
```

---

## 🧠 抓取策略 / Fetching Strategy

### 快路径优先，快路径不够再降级

```
fetch_fast.py（桌面 UA + curl + 正则，2–3s）
  ├─ 正文 ≥ 200 字 → ✅ 完成
  └─ 正文 < 200 字 / 命中验证码特征
        └─ wechat_article.py 四层降级链
```

### 四层降级链 / The 4-tier chain

```
URL → 验证码检测 / captcha detection
  ├─ 验证码 → Chrome 无头 → 仍被拦 → 搜狗转载搜索
  │           / Captcha → Chrome headless → still blocked → Sogou repost search
  └─ 正常 → meta 抽取 → CSR 正文空 → Chrome 兜底
            / Clean → meta extraction → CSR body empty → Chrome fallback
```

**四层的分工**：
- **Tier 0 验证码检测** — 必须最先跑。验证码页也有 `og:title`（没意义），不先排除会污染 meta。
- **Tier 1 meta 抽取** — 永远成功。哪怕正文全丢，至少拿到标题、作者、时间、封面。
- **Tier 2 curl 抓取** — `curl_cffi` 伪装 Chrome TLS JA3 指纹，1.5–3 秒。
- **Tier 3 Chrome headless** — CDP 驱动，等 JS 渲染完拿 SSR 后的 HTML（3–4MB），8–12 秒，成功率 >95%。
- **Tier 4 搜狗转载** — 最后一道防线，按标题找同文转载（跳转链接需人工点开）。

---

## 📋 输出格式 / Output Format

### 快路径 / Fast path

```markdown
# 文章标题

**发布时间**: 2026-06-10 20:00
**公众号**: 某某公众号
**原文链接**: https://mp.weixin.qq.com/s/xxx
**抓取方式**: curl + 桌面 UA (fast path)

---

[正文 Markdown，含图片链接与超链接]
```

### 四层链 / 4-tier chain

```markdown
# 文章标题

**Publish Time**: 2026-06-10
**Account**: Account Name
**Original Link**: https://mp.weixin.qq.com/s/xxx
**Cover**: https://mmbiz.qpic.cn/...
**Method**: curl_cffi

---

> 文章摘要（og:description）

[正文 Markdown（CSR 限制时为空）]

## 可能的转载链接（搜狗）
- [转载标题](https://weixin.sogou.com/link?url=...)
```

---

## 🧩 作为 Agent Skill 使用 / Use as an Agent Skill

本仓库同时是一个标准的 Agent Skill（`SKILL.md` 带 YAML frontmatter），可直接丢进 skill 目录：

| 平台 / Platform | 安装位置 / Where |
|---|---|
| Hermes Agent | `~/.hermes/skills/research/wechat-article/` |
| OpenClaw | `workspace/skills/wechat-article/` |
| Claude Code | `.claude/skills/wechat-article/` |

```bash
git clone https://github.com/Diyforfun2026/wechat-article-skill.git ~/.hermes/skills/research/wechat-article
```

作为 skill 使用时，Agent 会自动按上文策略选路径，并遵守纯图片合集等特殊场景的处理约定。

---

## 📚 文档 / Documentation

| 文档 | Doc |
|---|---|
| [SKILL.md](SKILL.md) — 完整使用文档（安装、API、限制、FAQ） | Full usage docs (install, API, limitations, FAQ) |
| [references/fast-path.md](references/fast-path.md) — 快路径原理、UA 关键点、正则边界坑 | Fast-path mechanics, the UA gotcha, the regex-boundary trap |
| [references/wechat-anti-crawl.md](references/wechat-anti-crawl.md) — 反爬技术细节与已验证的解决方案 | Anti-crawl technical details and verified solutions |
| [references/pure-image-articles.md](references/pure-image-articles.md) — 纯图片长图文章（headless 抓不到）的诊断与应对 | Diagnosing and handling pure-image articles that headless can't read |
| [references/collection-article-pattern.md](references/collection-article-pattern.md) — 合集文章 + GitHub 仓库的标准处理流程 | Standard flow for collection articles + GitHub repos |
| [references/changelog.md](references/changelog.md) — 版本变更记录 | Version changelog |

---

## ⚠️ 已知限制 / Known Limitations

| 场景 | 表现 | 应对 |
|---|---|---|
| 纯图片长图文章（`#js_image_content`） | 正文 100% 在图片里，非微信内置浏览器看不到 | 需用手机微信打开手动保存图片 + OCR，见 [references/pure-image-articles.md](references/pure-image-articles.md) |
| 验证码墙（"环境异常"） | meta 为空 | Chrome 兜底（80%+ 可过）→ 搜狗转载 |
| CSR 动态渲染 | curl 拿到 `js_content` 为空 | 快路径换桌面 UA；仍空则 Chrome 兜底 |
| 视频 / 音频内嵌 | 简化成 `<video>` / `<audio>` 标签 | 渲染器需支持 |
| 大图懒加载 | `data-src` 未解析 | 待优化 |
| 搜狗跳转链接 | 不是 `mp.weixin.qq.com` URL | 用户手动点开 |

---

## 🏷 主题 / Tags

**中文**：微信公众号实用工具 · 公众号文章抓取 · 微信反爬对抗 · AI Agent 技能

**English**: `wechat` · `mp-weixin` · `wechat-article` · `wechat-official-account` · `article-fetcher` · `anti-crawl` · `captcha` · `scraper` · `python` · `ai-agent` · `agent-skill` · `claude-code` · `hermes-agent` · `openclaw` · `markdown`

> GitHub topics 只接受小写字母 / 数字 / 连字符，中文标签放这里（GitHub 会自动索引 README 正文里的标签词）。

---

## 🤝 参与贡献 / Contributing

Issues 和 PR 都欢迎！值得做的方向：

- [ ] 懒加载图片处理（`data-src` → `src`）
- [ ] 表格转 Markdown
- [ ] Docker 镜像 / pip 包
- [ ] 更多反爬策略适配器

---

## 📄 许可证 / License

MIT — 中国用户随便用、随便改、随便商用，欢迎 PR。
MIT — free to use, modify, and ship. PRs welcome.
