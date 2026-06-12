# Changelog

## 1.0.0 — 2026-06-12

### 架构
- 4 层降级链：captcha_check → meta_extract → curl_cffi_fetch → sogou_search
- Chrome headless 集成：走 Chrome DevTools Protocol (CDP) via `websocket-client`

### 新增
- **`scripts/strategies/chrome_fetch.py`**: 独立 Chrome 实例 headless 抓取
  - 启动 `--headless=new` + 临时 `--user-data-dir` 隔离
  - CDP 通信：导航 → 等 Page.loadEventFired → 额外 JS 渲染等待
  - 25s 超时自动 kill，不留后台进程
- **主入口 `wechat_article.py`**:
  - `--no-chrome` CLI 参数
  - `--json` 输出模式
  - `--no-content` 仅 meta 模式
  - `--sogou` 搜狗搜索模式
  - CSR/Captcha 自动 Chrome 兜底

### 修复
- 修复 `captcha_check.py` 误判：旧规则 `window.cgiData\s*=` 将 `window.cgiDataNew` 误判为 captcha
  - 改为精确匹配：`cap_appid\s*[:=]\s*["']?\d{6,}` + 完整短语组合

### 验证数据
| 测试场景 | 结果 |
|---------|------|
| 无验证码文章（3 例） | curl_cffi 直通，获取全正文 |
| CSR + captcha 双重限制 | Chrome 拿到完整正文（4K+ 字符） |
| captcha 墙 | Chrome 突破成功（3.9K 字符正文） |
| Sogou 转载搜索 | 命中同标题转载文章 |

### 技术细节
- **URL 标准化**（`scripts/url_normalize.py`）: 9 对引号/角括号包壳处理 + HTML entity 解码 + 强制 https
- **HTML→Markdown**（`scripts/strategies/curl_cffi_fetch.py`）:
  - 块级元素 → 换行，`<a>` → `[text](href)`，`<img>` → `![alt](src)`
  - 12 个垃圾标签过滤（script, style, noscript 等）
  - 7 个微信特有选择器清除（分享提示、二维码、工具栏等）
- **验证码检测**（7 种特征）: TCaptcha JS, cap_appid, "环境异常" 等
- **Sogou 搜索**（`scripts/strategies/sogou_search.py`）:
  - URL 构造 + UA + Referer
  - 以 `id="sogou_vr_\d+_box_\d+"` 锚定真正结果（避免顶部导航 li 干扰）
  - 图片链接过滤（跳过 `sogou_vr_\d+_img_\d+` 和 `article_image_*`）
  - 时间字段清洗（去掉 `document.write(timeConvert('...'))` JS 占位）

### 自创设计
- 验证码检测必须先于 meta（captcha 页面也有 og:title，无意义）
- `fallback_urls` 字段：captcha 命中时自动搜 Sogou 找转载
- 4 层降级链的顺序设计：快（curl）→ 重（Chrome）→ 兜底（Sogou）

### 已知方向（待社区贡献）
- [ ] 懒加载图片处理（`data-src` → `src`）
- [ ] 表格转 Markdown
- [ ] 登录态 cookie 支持
- [ ] Docker 镜像 / pip 包
