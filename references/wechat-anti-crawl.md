# WeChat Anti-Crawl Strategies (Battle-Tested Notes)

> Continuously updated. Each entry is a verified failure mode + working solution.

## Approaches That Failed

### 1. Plain `requests.get` on WeChat
- **Symptom**: 80% of articles rate-limited / returned "环境异常" (environment abnormal) page
- **Cause**: Python `requests` TLS fingerprint is identified as non-browser
- **Solution**: Must use `curl_cffi` to impersonate Chrome JA3

### 2. Web Archive (web.archive.org) for body
- **Symptom**: HTML contains the `js_content` container, but its inner body is empty
- **Cause**: WeChat uses CSR; the body content is not in the initial HTML
- **Solution**: Web Archive can only fall back to meta-level data

### 3. jina.ai alone
- **Symptom**: In some network environments (especially pure IPv6), `r.jina.ai` times out repeatedly
- **Cause**: IPv6 routing compatibility issues
- **Solution**: No external services — pure local `curl_cffi` + Chrome

## Approaches That Work

### A. Direct `curl_cffi` Fetch
- **Scenario**: Non-captcha articles
- **Latency**: 1.5–3s
- **Output**: full meta, but `js_content` body often empty (CSR limitation)
- **Code**: `scripts/strategies/curl_cffi_fetch.py::fetch(url, prefer="curl_cffi")`

### B. Meta Tag Extraction
- **Scenario**: **All** non-captcha articles
- **Latency**: <100ms
- **Output**: title, description, author, cover, publish time
- **Code**: `scripts/strategies/meta_extract.py::extract_meta(html)`

### C. Chrome Headless Fallback
- **Scenario**: captcha wall / CSR body empty
- **Latency**: 8–12s (includes launch + JS render + DOM retrieval)
- **Output**: full post-SSR HTML (3–4 MB)
- **Code**: `scripts/strategies/chrome_fetch.py::fetch_with_chrome(url)`

### D. Sogou WeChat Search
- **Scenario**: Find reposts (bypass captcha)
- **Latency**: 1–2s
- **Output**: list of reposts with the same title
- **Caution**: Sogou has its own rate limit ("访问过于频繁" / too-frequent access), keep below 5 QPS
- **Code**: `scripts/strategies/sogou_search.py::search(query)`

### E. html_to_markdown
- **Scenario**: After obtaining the `#js_content` container
- **Supported**: paragraphs / headings / links / images / bold / italic / code blocks
- **Not supported**: complex tables / math formulas / nested lists
- **Code**: `scripts/strategies/curl_cffi_fetch.py::html_to_markdown(html)`

## Captcha Detection Patterns

7 signature matches (any one hit → captcha):

```python
CAPTCHA_MARKERS = [
    r'captcha\.gtimg\.com/TCaptcha\.js',     # Tencent TCaptcha container
    r'cap_appid\s*[:=]\s*["\']?\d+',          # captcha config
    r'window\.cgiData\s*=',                    # legacy captcha container
    r'环境异常',                                # WeChat-specific prompt (env abnormal)
    r'请输入验证码',                            # requires manual input
    r'访问频繁',                                # frequency-based rate limit
    r'异常访问',                                # behaviour-based rate limit
]
```

`captcha_reason()` returns a human-readable reason (e.g. "TCaptcha captcha wall (cap_appid triggered)").

## Comparison of Fetch Methods

| Method                       | Captcha Articles              | Non-captcha Articles       |
|------------------------------|-------------------------------|----------------------------|
| `curl_cffi` + meta           | ✅ captcha detection accurate | ✅ full meta               |
| Fetch body `#js_content`     | ❌ (captcha)                  | ⚠️ CSR often empty         |
| Chrome headless              | ✅ (80%+ bypass rate)         | ✅ full body               |
| Sogou repost search          | ✅ (gets repost URLs)         | —                          |
| HTML → Markdown              | ❌ (captcha)                  | ✅ (when body present)     |

## Anti-Crawl Escalation Timeline

- **2025-Q4**: WeChat started tightening anti-crawl, ~30% of articles triggered captcha
- **2026-Q1**: WeChat rolled out stricter "环境异常" (env-abnormal) walls, blocking many read articles
- **2026-Q2**: Sogou WeChat Search still usable (~80% reachable), but rate-limit required

## Key Lessons

1. **Don't trust a single point in time**: the same article may have different captcha status from different IP / UA / time
2. **Keep the fallback chain short**: users can't wait for all 4 tiers to fail
3. **Meta is always trustworthy**: even with captcha, `og:description` is usually the real summary
4. **Captcha detection must run before meta**: captcha pages also have `og:title` (meaningless), must be filtered out first
5. **Don't stress-test Sogou**: high frequency → IP ban; recommend `sleep 2s` between calls
