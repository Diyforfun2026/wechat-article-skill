#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略：curl_cffi/requests 直接抓取 + HTML→Markdown 转换
- 优先 curl_cffi（伪装 TLS JA3 指纹，能过部分 Cloudflare/反爬）
- 降级到 requests
- 即使正文是 CSR（js_content 为空），仍能拿 meta
"""

from __future__ import annotations
import re
import sys
from typing import Optional
from dataclasses import dataclass

# User-Agent 选 Chrome 120，Windows NT（部分 CDN 对 macOS UA 不友好）
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class FetchResult:
    success: bool
    method: str  # "curl_cffi" | "requests" | "none"
    html: str = ""
    status_code: int = 0
    error: str = ""


def _try_curl_cffi(url: str, timeout: int = 15) -> FetchResult:
    """优先 curl_cffi（伪装 TLS 指纹）"""
    try:
        from curl_cffi import requests as cffi_requests  # type: ignore
    except ImportError:
        return FetchResult(success=False, method="none", error="curl_cffi not installed")

    try:
        r = cffi_requests.get(
            url,
            impersonate="chrome120",
            headers={
                "User-Agent": DEFAULT_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=timeout,
            allow_redirects=True,
        )
        if r.status_code != 200:
            return FetchResult(
                success=False,
                method="curl_cffi",
                status_code=r.status_code,
                error=f"HTTP {r.status_code}",
            )
        # 微信对文本响应通常 ~1MB，正文；验证码页 ~2KB
        return FetchResult(
            success=True,
            method="curl_cffi",
            html=r.text,
            status_code=200,
        )
    except Exception as e:
        return FetchResult(success=False, method="curl_cffi", error=str(e))


def _try_requests(url: str, timeout: int = 15) -> FetchResult:
    """降级到 requests（很多场景就够用了）"""
    try:
        import requests  # type: ignore
    except ImportError:
        return FetchResult(success=False, method="none", error="requests not installed")

    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": DEFAULT_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=timeout,
            allow_redirects=True,
        )
        if r.status_code != 200:
            return FetchResult(
                success=False,
                method="requests",
                status_code=r.status_code,
                error=f"HTTP {r.status_code}",
            )
        return FetchResult(
            success=True,
            method="requests",
            html=r.text,
            status_code=200,
        )
    except Exception as e:
        return FetchResult(success=False, method="requests", error=str(e))


def fetch(url: str, timeout: int = 15, prefer: str = "curl_cffi") -> FetchResult:
    """
    抓取 URL 原始 HTML。
    prefer: "curl_cffi" | "requests" | "auto"
    """
    if prefer == "curl_cffi":
        r = _try_curl_cffi(url, timeout)
        if r.success:
            return r
        # 降级
        r2 = _try_requests(url, timeout)
        if r2.success:
            return r2
        # 都不行——返回 curl_cffi 的错误（更具体）
        return r

    if prefer == "requests":
        r = _try_requests(url, timeout)
        if r.success:
            return r
        r2 = _try_curl_cffi(url, timeout)
        if r2.success:
            return r2
        return r

    # auto: 哪个能用用哪个
    r = _try_curl_cffi(url, timeout)
    if r.success:
        return r
    return _try_requests(url, timeout)


# ========================
# HTML → Markdown（简化版 Turndown 思路）
# ========================

STRIPPED_TAGS = [
    "script", "style", "noscript", "canvas", "form", "button",
    "dialog", "header", "footer", "nav", "aside", "svg",
]

# 微信特有的"垃圾"选择器（OpenCLI 用 cleanSelectors 注入）
WX_CLEAN_SELECTORS = [
    "script", "style", "noscript",
    "#js_share_notice",       # 分享提示
    "#js_pc_qr_code",         # 底部二维码
    "#js_toobar3",            # 工具栏
    ".qr_code_pc",            # 二维码区
    ".reward_area",           # 赞赏
    ".rich_media_tool",       # 工具条
    "#js_tags_section",       # 标签区
    ".weui_dialog",           # 弹窗
]


def extract_main_content(html: str) -> str:
    """
    从微信文章 HTML 提取 #js_content 内 HTML。
    失败时返回空串。
    """
    if not html:
        return ""

    # 微信正文容器
    m = re.search(
        r'<div[^>]*id=["\']js_content["\'][^>]*>(.*?)</div>\s*<script',
        html,
        re.S | re.I,
    )
    if m:
        return m.group(1)

    # 兜底：id="js_content"
    m = re.search(r'<div[^>]*id=["\']js_content["\'][^>]*>(.*)', html, re.S | re.I)
    if m:
        return m.group(1)

    return ""


def html_to_markdown(html: str, base_url: str = "") -> str:
    """
    极简 HTML→Markdown。
    比不上 Turndown，但能保留段落/图片/链接/粗体。
    """
    if not html:
        return ""

    s = html

    # 1) 去垃圾标签（开标签 + 闭标签）
    for tag in STRIPPED_TAGS:
        s = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", s, flags=re.S | re.I)
        s = re.sub(rf"<{tag}\b[^>]*/?>", "", s, flags=re.I)

    # 2) 微信特有选择器（粗略，按 id/class 模式）
    for sel in WX_CLEAN_SELECTORS:
        if sel.startswith("#"):
            sel_re = re.escape(sel[1:])
            s = re.sub(rf'<[^>]*id=["\']{sel_re}["\'][^>]*>.*?</[^>]+>', "", s, flags=re.S | re.I)
        elif sel.startswith("."):
            sel_re = re.escape(sel[1:])
            s = re.sub(rf'<[^>]*class=["\'][^"\']*{sel_re}[^"\']*["\'][^>]*>.*?</[^>]+>', "", s, flags=re.S | re.I)

    # 3) 块级元素 → 换行
    for tag in ("p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "section", "blockquote"):
        s = re.sub(rf"<{tag}\b[^>]*>", "\n\n", s, flags=re.I)
        s = re.sub(rf"</{tag}>", "\n", s, flags=re.I)
        s = re.sub(rf"<{tag}\b[^>]*/>", "\n", s, flags=re.I)

    # 4) 标题
    for i in range(1, 7):
        # 已经处理过开闭标签了，现在用占位符
        pass

    # 5) <a href="...">text</a> → [text](href)
    s = re.sub(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        lambda m: f"[{re.sub(r'<[^>]+>', '', m.group(2))}]({m.group(1)})",
        s,
        flags=re.S | re.I,
    )

    # 6) <img src="..." alt="..."> → ![alt](src)
    def img_repl(m: re.Match) -> str:
        src = m.group(1) or ""
        alt = (m.group(2) or "").strip()
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/") and base_url:
            from urllib.parse import urljoin
            src = urljoin(base_url, src)
        return f"![{alt}]({src})"
    s = re.sub(
        r'<img\b[^>]*src=["\']([^"\']+)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?[^>]*/?>',
        img_repl,
        s,
        flags=re.I,
    )

    # 7) <strong>/<b> → **xxx**
    s = re.sub(r"<(strong|b)\b[^>]*>(.*?)</\1>", r"**\2**", s, flags=re.S | re.I)

    # 8) <em>/<i> → *xxx*
    s = re.sub(r"<(em|i)\b[^>]*>(.*?)</\1>", r"*\2*", s, flags=re.S | re.I)

    # 9) <code> → `xxx`
    s = re.sub(r"<code\b[^>]*>(.*?)</code>", r"`\1`", s, flags=re.S | re.I)

    # 10) 去剩余所有 HTML 标签
    s = re.sub(r"<[^>]+>", "", s)

    # 11) HTML entities
    s = (
        s.replace("&amp;", "&")
         .replace("&lt;", "<")
         .replace("&gt;", ">")
         .replace("&quot;", '"')
         .replace("&nbsp;", " ")
         .replace("&#39;", "'")
    )

    # 12) 合并多余空行
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = s.strip()

    return s


if __name__ == "__main__":
    # 自测
    sample = '''
    <p>Hello <strong>world</strong>!</p>
    <p>This is a <a href="https://example.com">link</a>.</p>
    <p><img src="https://example.com/img.jpg" alt="测试图片"></p>
    <script>alert('xss')</script>
    '''
    print(html_to_markdown(sample))
