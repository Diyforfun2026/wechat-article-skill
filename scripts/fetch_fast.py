#!/usr/bin/env python3
"""
fetch_fast.py — 快路径抓取微信公众号文章正文（桌面 UA + curl + 正则）。

比 4 层降级链更快：不需要 curl_cffi、不需要启动 Chrome。
实测（2026-10-25，连续 3 篇）：每篇 2–3 秒，0 次 Chrome 启动，正文 5000–7000 字。

用法：
    python3 fetch_fast.py "https://mp.weixin.qq.com/s/<ID>"          # 打印正文
    python3 fetch_fast.py "https://mp.weixin.qq.com/s/<ID>" --title   # 只打印标题
    python3 fetch_fast.py "https://mp.weixin.qq.com/s/<ID>" --json    # JSON 输出
    python3 fetch_fast.py "https://mp.weixin.qq.com/s/<ID>" -o out.md # 写到文件

关键点：UA 必须是**桌面浏览器**，不要用微信内置浏览器 UA —— 后者常拿到 CSR 空
的 #js_content，逼你启动 Chrome。

何时回退到 wechat_article.py（4 层链）：
    - 抽出的正文 < 200 字（CSR 空）
    - 页面命中 captcha 特征（"环境异常" / 验证页）
"""

import argparse
import datetime
import html as html_mod
import json
import re
import subprocess
import sys

DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)

CAPTCHA_MARKERS = (
    "环境异常",
    "完成验证后即可继续访问",
    "该内容已被发布者删除",
    "此内容因违规无法查看",
)

# WeChat-specific UI blocks that follow the article body
WX_CLEAN_SELECTORS = [
    "script", "style", "noscript",
    "#js_share_notice",       # 分享提示
    "#js_pc_qr_code",         # 底部二维码
    "#js_toobar3",            # 工具条
    ".qr_code_pc",            # 二维码区
    ".reward_area",           # 赞赏区
    ".rich_media_tool",       # 文末互动条（点赞/在看/分享）
    "#js_tags_section",       # 标签区
    ".weui_dialog",           # 弹窗
]


def fetch(url: str, timeout: int = 30) -> str:
    """Plain curl with a desktop UA. Returns the raw HTML."""
    cmd = [
        "curl", "-sL", "-m", str(timeout),
        "-A", DESKTOP_UA,
        "-H", "Accept: text/html,application/xhtml+xml",
        "-H", "Accept-Language: zh-CN,zh;q=0.9",
        url,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    except subprocess.TimeoutExpired:
        return ""
    return out.stdout.decode("utf-8", errors="replace")


def get_meta(raw: str) -> dict:
    meta = {}
    for key, pattern in (
        ("title", r'<meta property="og:title" content="([^"]*)"'),
        ("description", r'<meta property="og:description" content="([^"]*)"'),
        ("author", r'<meta property="og:article:author" content="([^"]*)"'),
        ("image", r'<meta property="og:image" content="([^"]*)"'),
    ):
        m = re.search(pattern, raw)
        if m:
            meta[key] = html_mod.unescape(m.group(1))
    # publish_time appears as a JS var
    m = re.search(r'var\s*ct\s*=\s*"(\d+)"', raw)
    if m:
        meta["publish_time"] = datetime.datetime.fromtimestamp(
            int(m.group(1))
        ).strftime("%Y-%m-%d %H:%M")
    return meta


def extract_body_html(raw: str) -> str:
    """
    Extract the inner HTML of `#js_content`.

    Boundary order matters — a greedy `.*` swallows the ~2.9 MB of
    "微信扫一扫 / 点赞 / 在看" chrome that follows the article:
      1. non-greedy up to `</div><script` (what the main script uses)
      2. non-greedy up to `<div class="rich_media_tool`
      3. greedy fallback (last resort)
    """
    m = re.search(
        r'<div[^>]*id=["\']js_content["\'][^>]*>(.*?)</div>\s*<script',
        raw, re.S | re.I,
    )
    if m:
        return m.group(1)
    m = re.search(
        r'<div[^>]*id=["\']js_content["\'][^>]*>(.*?)<div class="rich_media_tool',
        raw, re.S | re.I,
    )
    if m:
        return m.group(1)
    m = re.search(r'<div[^>]*id=["\']js_content["\'][^>]*>(.*)', raw, re.S | re.I)
    return m.group(1) if m else ""


def strip_junk(s: str) -> str:
    """Remove WeChat UI blocks (share bar, QR code, reward area, ...)."""
    for sel in WX_CLEAN_SELECTORS:
        if sel.startswith("#"):
            sel_re = re.escape(sel[1:])
            s = re.sub(
                rf'<[^>]*id=["\']{sel_re}["\'][^>]*>.*?</[^>]+>',
                "", s, flags=re.S | re.I,
            )
        elif sel.startswith("."):
            sel_re = re.escape(sel[1:])
            s = re.sub(
                rf'<[^>]*class=["\'][^"\']*{sel_re}[^"\']*["\'][^>]*>.*?</[^>]+>',
                "", s, flags=re.S | re.I,
            )
        else:
            s = re.sub(rf"<{sel}\b[^>]*>.*?</{sel}>", "", s, flags=re.S | re.I)
            s = re.sub(rf"<{sel}\b[^>]*/?>", "", s, flags=re.I)
    return s


def html_to_text(body: str) -> str:
    """Convert the article body HTML to readable Markdown-ish text."""
    if not body:
        return ""

    s = strip_junk(body)

    # Links → [text](href)
    s = re.sub(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        lambda m: f"[{re.sub(r'<[^>]+>', '', m.group(2))}]({m.group(1)})",
        s, flags=re.S | re.I,
    )

    # Images → ![alt](src)  (protocol-relative URLs get https:)
    def img_repl(m: re.Match) -> str:
        src = m.group(1) or ""
        alt = (m.group(2) or "").strip()
        if src.startswith("//"):
            src = "https:" + src
        return f"![{alt}]({src})"

    s = re.sub(
        r'<img\b[^>]*src=["\']([^"\']+)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?[^>]*/?>',
        img_repl, s, flags=re.I,
    )

    # Inline formatting
    s = re.sub(r"<(strong|b)\b[^>]*>(.*?)</\1>", r"**\2**", s, flags=re.S | re.I)
    s = re.sub(r"<(em|i)\b[^>]*>(.*?)</\1>", r"*\2*", s, flags=re.S | re.I)
    s = re.sub(r"<code\b[^>]*>(.*?)</code>", r"`\1`", s, flags=re.S | re.I)

    # Block elements → newlines
    s = re.sub(r"</(p|div|section|h[1-6]|li|tr|blockquote)>", "\n\n", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</td>", " | ", s)
    s = re.sub(r"<h1\b[^>]*>", "\n\n# ", s, flags=re.I)
    s = re.sub(r"<h2\b[^>]*>", "\n\n## ", s, flags=re.I)
    s = re.sub(r"<h3\b[^>]*>", "\n\n### ", s, flags=re.I)

    # Strip remaining tags
    s = re.sub(r"<[^>]+>", "", s)

    # Unescape entities
    for a, b in (
        ("&nbsp;", " "), ("&quot;", '"'), ("&amp;", "&"),
        ("&lt;", "<"), ("&gt;", ">"), ("&#39;", "'"),
    ):
        s = s.replace(a, b)
    s = html_mod.unescape(s)

    # Tidy whitespace
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--title", action="store_true", help="print title only")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("-o", "--out", help="write body to this file")
    args = ap.parse_args()

    raw = fetch(args.url)
    if not raw:
        print("ERROR: empty response — fall back to wechat_article.py", file=sys.stderr)
        return 2

    meta = get_meta(raw)
    body = html_to_text(extract_body_html(raw))

    captcha = any(m in raw for m in CAPTCHA_MARKERS)
    if captcha:
        print("NOTE: captcha markers detected — fall back to wechat_article.py",
              file=sys.stderr)
    if len(body) < 200:
        print(f"NOTE: body only {len(body)} chars (CSR?) — fall back to "
              "wechat_article.py", file=sys.stderr)

    if args.title:
        print(meta.get("title", ""))
        return 0

    if args.json:
        print(json.dumps({
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "publish_time": meta.get("publish_time", ""),
            "description": meta.get("description", ""),
            "content_chars": len(body),
            "captcha": captcha,
            "content": body,
        }, ensure_ascii=False, indent=2))
        return 0

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(f"# {meta.get('title', '')}\n\n")
            if meta.get("publish_time"):
                f.write(f"**发布时间**: {meta['publish_time']}\n")
            if meta.get("author"):
                f.write(f"**公众号**: {meta['author']}\n")
            f.write(f"**原文链接**: {args.url}\n")
            f.write(f"**抓取方式**: curl + 桌面 UA (fast path)\n\n---\n\n")
            f.write(body)
            f.write("\n")
        print(f"wrote {args.out} ({len(body)} chars)")
        return 0

    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
