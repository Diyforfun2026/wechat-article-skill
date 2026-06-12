# WeChat Article Fetcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

微信公众号文章抓取工具 — 4 层降级策略应对反爬墙和 CSR 动态渲染。

## 亮点

- **80% 文章 1.5-3s** 完成（curl_cffi 伪装 TLS JA3 指纹）
- **Chrome headless 兜底**：captcha 墙和 CSR 空正文不再头疼
- **Sogou 转载搜索**：验证码墙后的最后一道防线
- **零外部依赖**：不依赖 jina.ai / 任何第三方 API
- **跨平台兼容**：纯 Python 脚本，Hermes Agent / OpenClaw / Claude Code / 任何 CLI 均可用
- **结构化输出**：Markdown 或 JSON，适合程序化处理

## 快速开始

```bash
# 安装依赖
pip install requests curl_cffi websocket-client

# 抓一篇试试
python3 scripts/wechat_article.py "https://mp.weixin.qq.com/s/xxx"
```

## 抓取策略

```
URL → captcha 检测
  ├─ 验证码 → Chrome headless → 仍被拦 → Sogou 找转载
  └─ 正常 → meta 提取 → CSR 正文空 → Chrome 兜底
```

## 文档

- [SKILL.md](SKILL.md) — 完整使用文档（安装、API、限制、FAQ）
- [references/wechat-anti-crawl.md](references/wechat-anti-crawl.md) — 反爬技术细节与验证过的方案

## 协议

MIT
