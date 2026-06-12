# 微信公众号反爬应对（实战经验汇总）

> 持续更新。每条都是经过验证的失败模式 + 应对方案。

## 验证失败的方案

### 1. 单纯 `requests.get` 微信

- **现象**: 80% 文章被风控 / 返回 "环境异常" 页面
- **原因**: Python requests 的 TLS 指纹被识别为非浏览器
- **应对**: 必须用 `curl_cffi` 伪装 Chrome JA3

### 2. Web Archive (web.archive.org) 抓正文

- **现象**: HTML 含 js_content 容器，但内部为空
- **原因**: 微信 CSR 动态渲染，正文内容不在初始 HTML
- **应对**: Web Archive 只能降级到 meta 级别

### 3. 仅 jina.ai 抓取

- **现象**: 部分网络环境（尤其是纯 IPv6）下 r.jina.ai 持续超时
- **原因**: IPv6 路由兼容性问题
- **应对**: 不依赖外部服务，纯本地 curl_cffi + Chrome

## 验证有效的方案

### A. curl_cffi 直接抓

- **场景**: 无验证码文章
- **耗时**: 1.5-3s
- **产出**: meta 完整，正文 js_content 经常空（CSR 限制）
- **代码**: `scripts/strategies/curl_cffi_fetch.py::fetch(url, prefer="curl_cffi")`

### B. Meta 标签提取

- **场景**: **所有**非验证码文章
- **耗时**: <100ms
- **产出**: 标题、描述、作者、封面、发布时间
- **代码**: `scripts/strategies/meta_extract.py::extract_meta(html)`

### C. Chrome headless 兜底

- **场景**: captcha 墙 / CSR 正文为空
- **耗时**: 8-12s（含启动 + JS 渲染 + DOM 抓取）
- **产出**: 完整 SSR 后 HTML（3-4MB）
- **代码**: `scripts/strategies/chrome_fetch.py::fetch_with_chrome(url)`

### D. 搜狗微信搜索（Sogou）

- **场景**: 找转载页（绕过 captcha）
- **耗时**: 1-2s
- **产出**: 同标题转载列表
- **注意**: Sogou 自身有风控（"访问过于频繁"），频次不要超过 5 QPS
- **代码**: `scripts/strategies/sogou_search.py::search(query)`

### E. html_to_markdown

- **场景**: 拿到 #js_content 容器后提取正文
- **支持**: 段落/标题/链接/图片/粗体/斜体/代码块
- **不支持**: 复杂表格/数学公式/嵌套列表
- **代码**: `scripts/strategies/curl_cffi_fetch.py::html_to_markdown(html)`

## 验证码识别模式

7 种特征匹配（任一命中即判定 captcha）：

```python
CAPTCHA_MARKERS = [
    r'captcha\.gtimg\.com/TCaptcha\.js',     # 腾讯 TCaptcha 容器
    r'cap_appid\s*[:=]\s*["\']?\d+',          # captcha 配置
    r'window\.cgiData\s*=',                    # 老版 captcha 容器
    r'环境异常',                                # 微信特定提示
    r'请输入验证码',                            # 需手动输入
    r'访问频繁',                                # 频次风控
    r'异常访问',                                # 行为风控
]
```

`captcha_reason()` 返回人类可读的原因（如 "TCaptcha 验证码墙（cap_appid 触发）"）。

## 各抓取方式对比

| 方式 | 验证码文章 | 无验证码文章 |
|------|-----------|------------|
| curl_cffi + meta | ✅ captcha 检测准确 | ✅ meta 完整 |
| 抓正文 #js_content | ❌（captcha） | ⚠️ CSR 经常空 |
| Chrome headless | ✅（80%+ 突破率） | ✅ 正文完整 |
| Sogou 搜转载 | ✅（拿到转载网址） | — |
| HTML→Markdown | ❌（captcha） | ✅（有正文时） |

## 反爬升级时间线

- **2025-Q4**: 微信开始加强反爬，约 30% 文章触发 captcha
- **2026-Q1**: 微信上线更严格的"环境异常"墙，大量阅读文章被拦
- **2026-Q2**: Sogou 微信搜索仍可用（约 80% 可达），需控制频次

## 关键学习

1. **不要相信单点**: 同一篇文章在不同 IP/UA/时间可能 captcha 状态不同
2. **降级链要短**: 用户等不了 4 层降级全部失败
3. **Meta 永远可信**: 即使 captcha，og:description 通常是真实摘要
4. **captcha 检测必须先于 meta**：captcha 页面也有 og:title（无意义），必须先排除
5. **Sogou 不要压测**: 频次高了直接封 IP，建议 sleep 2s
