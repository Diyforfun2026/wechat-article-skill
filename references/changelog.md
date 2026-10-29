# Changelog

## 1.2.0 — 2026-10-30

### Added
- **`scripts/fetch_fast.py`** — fast path: desktop-browser UA + plain `curl` + regex extraction.
  - 2–3 s per article, **zero third-party dependencies, zero Chrome launches**
  - A desktop UA makes WeChat server-render `#js_content`; the WeChat in-app UA does not
  - Supports `--title`, `--json`, `-o out.md`
  - Prints a `NOTE:` to stderr when the body is under 200 chars or a captcha marker is present —
    that is the signal to fall back to the 4-tier chain
- **`references/fast-path.md`** — why the fast path works, and the extraction-boundary trap
  (a greedy `.*` swallows ~2.9 MB of trailing WeChat UI chrome)
- **`references/pure-image-articles.md`** — the `#js_image_content` format: 5 diagnostic signals,
  a 2-second diagnosis snippet, and the honest "ask the user to send the images" workflow
- **`references/collection-article-pattern.md`** — collection article + GitHub repo handling flow
  (fetch the collection, list `examples/`, pull the README via jsdelivr, then stop)
- **`LICENSE`** — the MIT file the README badge already pointed at (it was a 404)

### Fixed
- `fetch_fast.py` extraction boundary: bounded (non-greedy) match up to `</div><script`, falling back
  to `<div class="rich_media_tool"` — the greedy version produced a body ending in several hundred
  lines of "微信扫一扫 / 赞 / 在看" UI garbage
- `fetch_fast.py` now strips WeChat-specific UI selectors (`rich_media_tool`, `qr_code_pc`,
  `reward_area`, `js_pc_qr_code`, …), the same `WX_CLEAN_SELECTORS` list the 4-tier chain uses
- `fetch_fast.py` now preserves links, images, headings and inline formatting instead of flattening
  everything to plain text

### Changed
- `README.md` — rewritten in Chinese-first bilingual form: two fetching paths, an Agent-skill
  install section, a known-limitations table, and a tag list
- `SKILL.md` — version 1.2.0; documents the fast path, the path-selection table, and the
  fast-path/fallback rule
- Repository topics set for discoverability

## 1.1.0 — 2026-06-15

### Internationalisation
- Full English translation of all user-facing documentation: `README.md`, `SKILL.md`, `references/changelog.md`, `references/wechat-anti-crawl.md`
- All Python scripts (`scripts/wechat_article.py` + 5 strategy modules) — docstrings, comments, and CLI output translated to English
- YAML frontmatter `description` in `SKILL.md` rewritten in English
- Goal: make the skill accessible to all WeChat-content developers worldwide

## 1.0.0 — 2026-06-12

### Architecture
- 4-tier fallback chain: `captcha_check` → `meta_extract` → `curl_cffi_fetch` → `sogou_search`
- Chrome headless integration: communicates via Chrome DevTools Protocol (CDP) using `websocket-client`

### Added
- **`scripts/strategies/chrome_fetch.py`**: independent Chrome instance headless fetcher
  - Launches `--headless=new` with a temporary `--user-data-dir` for isolation
  - CDP communication: navigate → wait for `Page.loadEventFired` → extra JS-render wait
  - 25s auto-kill timeout, no background processes left behind
- **Main entry `wechat_article.py`**:
  - `--no-chrome` CLI flag
  - `--json` output mode
  - `--no-content` meta-only mode
  - `--sogou` Sogou-search mode
  - Automatic Chrome fallback for CSR / captcha

### Fixed
- Fixed `captcha_check.py` false positive: the old rule `window.cgiData\s*=` would mis-flag `window.cgiDataNew` as captcha
  - Replaced with exact matches: `cap_appid\s*[:=]\s*["']?\d{6,}` + full phrase combinations

### Validation Data

| Test Scenario                     | Result                                            |
|-----------------------------------|---------------------------------------------------|
| Non-captcha articles (3 cases)    | `curl_cffi` direct, full body retrieved           |
| CSR + captcha double-restriction  | Chrome got full body (4K+ chars)                  |
| Captcha wall                      | Chrome bypass succeeded (3.9K char body)          |
| Sogou repost search               | Hit repost articles with the same title           |

### Technical Details
- **URL normalisation** (`scripts/url_normalize.py`): 9 quote/angle-bracket wrapping pairs + HTML entity decoding + force-https
- **HTML → Markdown** (`scripts/strategies/curl_cffi_fetch.py`):
  - Block elements → newlines, `<a>` → `[text](href)`, `<img>` → `![alt](src)`
  - 12 junk-tag filters (script, style, noscript, etc.)
  - 7 WeChat-specific selector removals (share notices, QR codes, toolbars, etc.)
- **Captcha detection** (7 signatures): TCaptcha JS, `cap_appid`, "环境异常" (environment abnormal), etc.
- **Sogou search** (`scripts/strategies/sogou_search.py`):
  - URL construction + UA + Referer
  - Anchor on real results via `id="sogou_vr_\d+_box_\d+"` (avoid top-nav `li` interference)
  - Image link filtering (skip `sogou_vr_\d+_img_\d+` and `article_image_*`)
  - Time field cleaning (strip `document.write(timeConvert('...'))` JS placeholders)

### Original Design Choices
- Captcha detection must run before meta (captcha pages also have `og:title`, which is meaningless)
- `fallback_urls` field: automatically search Sogou for reposts when captcha hits
- 4-tier chain order: fast (curl) → heavy (Chrome) → fallback (Sogou)

### Known Areas (Community Contributions Welcome)
- [ ] Lazy-loaded image handling (`data-src` → `src`)
- [ ] Table-to-Markdown
- [ ] Login-state cookie support
- [ ] Docker image / pip package
