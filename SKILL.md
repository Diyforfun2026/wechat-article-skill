---
name: wechat-article
description: 微信公众号文章抓取工具 — 4 层降级策略（captcha 检测 → meta 提取 → Chrome headless → Sogou 转载搜索）。支持 Markdown/JSON 输出，适配 CSR 动态渲染和反爬墙。
version: 1.0.0
author: wechat-article-skill contributors
license: MIT
---

# WeChat Article Fetcher

微信公众号文章抓取工具，通过 4 层降级策略最大程度获取文章内容。针对微信的 CSR（客户端渲染）和反爬墙做了专项优化。

## 目录

- [特性](#特性)
- [安装](#安装)
- [抓取策略（4 层降级）](#抓取策略4-层降级)
- [用法](#用法)
- [输出格式](#输出格式)
- [API（Python 库模式）](#apipython-库模式)
- [依赖与兼容性](#依赖与兼容性)
- [已知限制](#已知限制)
- [FAQ](#faq)

## 特性

- **80% 文章 1.5-3s 完成**（curl_cffi 伪装 TLS JA3 指纹）
- **验证码墙自动绕过** → 优先 Chrome headless 突破 → 仍失败则 Sogou 找转载
- **CSR 动态渲染文章** → Chrome headless 兜底抓 SSR 后 HTML（3-4MB，含完整正文）
- **输出结构化 Markdown**（标题/作者/发布时间/封面/正文）
- **Curl 级速度 + 浏览器级兜底** 两全
- **跨 AI Agent 平台兼容** — 纯 Python 脚本，不绑定任何 Agent 框架（Hermes Agent / OpenClaw / Claude Code / 任何 CLI 均可用）

## 安装

### 依赖

| 依赖 | 版本要求 | 用途 |
|------|---------|------|
| Python | 3.9+ | 运行时 |
| `requests` | 任意 | 降级 HTTP 抓取 |
| `curl_cffi` | 任意 | 主 HTTP 抓取（伪装 TLS JA3 指纹） |
| `websocket-client` | 任意 | Chrome DevTools Protocol（CDP）通信 |
| Google Chrome / Chromium | 148+ | **可选** — 仅 captcha/CSR 文章需要 |

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/wechat-article-skill.git
cd wechat-article-skill

# 2. 安装 Python 依赖
pip install requests curl_cffi websocket-client

# 3. （可选）安装 Chrome
# 如果没有 Chrome，部分受 captcha 或 CSR 限制的文章无法获取完整正文。
# 但 meta 信息（标题/作者/时间/封面）始终可以获取。
```

## 抓取策略（4 层降级）

```
URL → captcha_check（必须先于 meta）
  ├─ 验证码 → 优先 Chrome headless 突破
  │             └─ 仍被拦 → Sogou 搜索找转载
  └─ 无验证码 → meta 提取
       └─ CSR 空（正文 < 200 字符）→ Chrome headless 兜底
            └─ Chrome 也失败 → meta 完整保留，正文为空
```

**关键洞察**：
- 微信文章正文是 **CSR 动态渲染** → curl 拿到的 `#js_content` 经常为空
- 但 **meta 标签（og:title, og:description, og:image, publish_time）始终可读**
- captcha 阻挡的文章 → 用 Sogou 搜同标题转载，聚合到 `fallback_urls`
- Chrome headless 可在 **8-12s** 内抓完整 SSR 后 HTML（3-4MB）

### 各策略详解

#### 第 0 层：验证码检测（必须最先执行）
- 7 种特征匹配：TCaptcha JS、cap_appid、"环境异常"、"请输入验证码"、"访问频繁"等
- **为什么先于 meta**：captcha 页面也有 og:title（无意义的验证码页标题），必须先排除

#### 第 1 层：Meta 提取（永远成功）
- 解析 HTML meta 标签：`og:title`, `og:description`, `og:image`, `og:article:author`, `og:article:published_time`
- 公众号名称从 `<strong class="profile_meta_nickname">` 提取
- **永远不失败** — 即使验证码和 Chrome 都失败，meta 至少提供文章标题和摘要

#### 第 2 层：Curl 抓取（最快）
- **优先 `curl_cffi`**：伪装 Chrome 120 的 TLS JA3 指纹，能过大部分 Cloudflare/微信反爬
- 降级到 `requests`（很多场景也够用）
- 对无验证码文章，1.5-3s 完成；正文可能为空（CSR 限制）

#### 第 3 层：Chrome headless 兜底（最重但最准）
- 启动独立 Chrome 实例（`--headless=new`），使用临时 `--user-data-dir` 隔离
- 通过 Chrome DevTools Protocol（CDP）导航、等渲染、取 DOM
- 适用于：
  - captcha 突破（80%+ 成功率）
  - CSR 正文抓取（curl 拿不到 `#js_content` 内容时）
- 每次调用启动+清理，**不留后台进程**
- 25s 超时自动 kill

#### 第 4 层：Sogou 转载搜索（最后兜底）
- 当 captcha 墙无法突破时，用文章标题搜索 Sogou 微信搜索
- 返回同标题的转载文章列表（含 publisher, summary, publish_time）
- **限制**：Sogou 跳转链接无法自动 resolve 到 mp.weixin.qq.com URL（服务端加密 + antispider），用户需要手动点击 Sogou 链接访问原文

## 用法

### 抓取单篇文章

```bash
# 默认模式（自动启用 Chrome 兜底）
python3 scripts/wechat_article.py "https://mp.weixin.qq.com/s/abc"

# 禁用 Chrome（只用 curl_cffi + Sogou，更快但无正文）
python3 scripts/wechat_article.py --no-chrome "https://mp.weixin.qq.com/s/abc"

# 只拿 meta（最快，用于只想看摘要的场景）
python3 scripts/wechat_article.py --no-content "https://mp.weixin.qq.com/s/abc"
```

### JSON 输出

```bash
python3 scripts/wechat_article.py --json "https://mp.weixin.qq.com/s/abc" | jq .
# 关键字段: method（curl_cffi/chrome_headless）, chrome_used（bool）, content_chars
```

### Sogou 搜索找转载（绕过 captcha）

```bash
python3 scripts/wechat_article.py --sogou "文章标题关键词"
# 输出：列表含 Sogou 跳转链接（用户需要手动点击跳到原文）
```

### 批量处理

```bash
cat urls.txt | while read url; do
  python3 scripts/wechat_article.py "$url" > "out_$(date +%s).md"
done
```

## 输出格式

```markdown
# 文章标题

**发布时间**: 2026-06-10
**公众号**: 公众号名称
**原文链接**: https://mp.weixin.qq.com/s/abc
**封面**: https://mmbiz.qpic.cn/...
**抓取方式**: curl_cffi

---

> 这是文章摘要（og:description）

[正文 Markdown（CSR 限制时可能为空）]

## 可能的转载链接（搜狗）
- [转载标题](https://weixin.sogou.com/link?url=...)
```

## API（Python 库模式）

```python
from scripts.wechat_article import fetch_article

result = fetch_article(
    "https://mp.weixin.qq.com/s/abc",
    want_content=True,      # 是否抓正文
    timeout=15,              # curl 超时
    use_chrome=True,         # 正文为空时启用 Chrome 兜底
)

print(f"成功: {result.success}")
print(f"方式: {result.method}")
print(f"标题: {result.title}")
print(f"公众号: {result.account}")
print(f"发布时间: {result.publish_time}")
print(f"正文: {result.content_md[:200]}...")
```

## 依赖与兼容性

| 环境 | 兼容性 |
|------|--------|
| macOS | ✅ 完整支持（Chrome headless + curl_cffi） |
| Linux | ✅ 需要安装 Chromium/Chrome 以启用 headless 兜底 |
| Windows | ⚠️ 理论可运行（未测试） |
| Docker | ⚠️ 需要 `--no-sandbox` 参数（已内置） |

### 各抓取路径耗时

| 路径 | 耗时 | 成功率 | 备注 |
|------|------|--------|------|
| curl_cffi（直通） | 1.5-3s | ~80% 无验证码 | 正文可能 CSR 空 |
| Chrome headless | 8-12s | >95% | 含启动 + JS 渲染 |
| Sogou 转载搜索 | 1-2s | ~80% | 不保证命中 |

### Python 版本兼容

| 特性 | 3.9+ | 3.8 | <3.8 |
|------|------|-----|------|
| `from __future__ import annotations` | ✅ | ✅ | ❌ |
| `dataclasses` | ✅ | `pip install dataclasses` | ❌ |
| `urllib.request` | ✅ | ✅ | ✅ |
| `websocket-client` | ✅ | ✅ | ✅ |

> **推荐 Python 3.9+**

## 已知限制

| 场景 | 说明 | 应对 |
|------|------|------|
| 验证码墙（"环境异常"） | meta 为空 | Chrome 突破（80%+ 能过）→ 仍失败 → Sogou 转载 |
| CSR 动态渲染 | curl 拿 js_content 为空 | Chrome headless 抓 SSR 后 HTML |
| 视频/音频嵌入 | Turndown 简化为 `<video>`/`<audio>` 标签 | Markdown 渲染器需支持 |
| 大图懒加载 | `data-src` 没解析 | 待优化 |
| 24 小时阅读量限制 | 老文章无 publish_time 字段 | 仅 og:title/description 可信 |
| Sogou 跳转链接 | 不是 mp.weixin.qq.com URL | 用户需要手动点击链接访问 |

## FAQ

### Q: 为什么不用 jina.ai / r.jina.ai？
jina.ai 在某些网络环境下 IPv6 不可达导致超时。本工具完全不依赖外部服务，纯本地自建。

### Q: 需要登录微信吗？
不需要。当前版本不实现登录态。如果未来需要支持需要登录的文章，可通过 Chrome 导出 cookie 到 `wechat.cookies` 文件启用。

### Q: Sogou 搜索会被封 IP 吗？
Sogou 有频次风控。建议不要超过 5 QPS，调用间至少 sleep 2s。代码中已有风控检测（验证码/安全验证/访问过于频繁），命中时自动返回空结果。

### Q: 可以不装 Chrome 吗？
可以。加了 `--no-chrome` 参数后，受 captcha 或 CSR 限制的文章无法获取正文，但 meta 信息（标题、作者、时间、封面）始终可获取。

## 贡献

欢迎 Issue / PR！可以关注以下几个方向：

- [ ] 懒加载图片处理（`data-src` → `src`）
- [ ] 表格转 Markdown
- [ ] Docker 镜像 / pip 包
- [ ] 更多反爬策略适配
