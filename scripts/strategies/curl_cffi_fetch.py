#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strategy: curl_cffi/requests direct fetch + HTML→Markdown conversion.

- Prefers curl_cffi (impersonates TLS JA3 fingerprint, bypasses some Cloudflare/anti-crawl)
- Falls back to requests
- Even when the body is CSR (js_content empty), meta can still be retrieved
"""

from __future__ import annotations
import re
import sys
from typing import Optional
from dataclasses import dataclass

# User-Agent picks Chrome 120 on Windows NT (some CDNs are unfriendly to macOS UA)
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
    """Prefers curl_cffi (impersonates TLS fingerprint)."""
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
        # WeChat text responses are typically ~1MB with body; captcha pages are ~2KB
        return FetchResult(
            success=True,
            method="curl_cffi",
            html=r.text,
            status_code=200,
        )
    except Exception as e:
        return FetchResult(success=False, method="curl_cffi", error=str(e))


def _try_requests(url: str, timeout: int = 15) -> FetchResult:
    """Falls back to requests (sufficient in many cases)."""
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
    Fetch the raw HTML of a URL.

    prefer: "curl_cffi" | "requests" | "auto"
    """
    if prefer == "curl_cffi":
        r = _try_curl_cffi(url, timeout)
        if r.success:
            return r
        # Fallback
        r2 = _try_requests(url, timeout)
        if r2.success:
            return r2
        # Both failed — return the curl_cffi error (more specific)
        return r

    if prefer == "requests":
        r = _try_requests(url, timeout)
        if r.success:
            return r
        r2 = _try_curl_cffi(url, timeout)
        if r2.success:
            return r2
        return r

    # auto: whichever works
    r = _try_curl_cffi(url, timeout)
    if r.success:
        return r
    return _try_requests(url, timeout)


# ========================
# HTML → Markdown (simplified Turndown-style)
# ========================

STRIPPED_TAGS = [
    "script", "style", "noscript", "canvas", "form", "button",
    "dialog", "header", "footer", "nav", "aside", "svg",
]

# WeChat-specific "junk" selectors (OpenCLI injects these via cleanSelectors)
WX_CLEAN_SELECTORS = [
    "script", "style", "noscript",
    "#js_share_notice",       # Share notice
    "#js_pc_qr_code",         # Bottom QR code
    "#js_toobar3",            # Toolbar
    ".qr_code_pc",            # QR code area
    ".reward_area",           # Tip / reward area
    ".rich_media_tool",       # Rich-media toolbar
    "#js_tags_section",       # Tag area
    ".weui_dialog",           # Pop-up dialog
]


def extract_main_content(html: str) -> str:
    """
    Extract the inner HTML of `#js_content` from a WeChat article.

    Returns an empty string on failure.
    """
    if not html:
        return ""

    # WeChat body container
    m = re.search(
        r'<div[^>]*id=["\']js_content["\'][^>]*>(.*?)</div>\s*<script',
        html,
        re.S | re.I,
    )
    if m:
        return m.group(1)

    # Fallback: id="js_content"
    m = re.search(r'<div[^>]*id=["\']js_content["\'][^>]*>(.*)', html, re.S | re.I)
    if m:
        return m.group(1)

    return ""


def html_to_markdown(html: str, base_url: str = "") -> str:
    """
    Minimal HTML → Markdown converter.

    Not as good as Turndown, but preserves paragraphs / images / links / bold / italic.
    """
    if not html:
        return ""

    s = html

    # 1) Strip junk tags (open + close)
    for tag in STRIPPED_TAGS:
        s = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", s, flags=re.S | re.I)
        s = re.sub(rf"<{tag}\b[^>]*/?>", "", s, flags=re.I)

    # 2) WeChat-specific selectors (rough, by id/class pattern)
    for sel in WX_CLEAN_SELECTORS:
        if sel.startswith("#"):
            sel_re = re.escape(sel[1:])
            s = re.sub(rf'<[^>]*id=["\']{sel_re}["\'][^>]*>.*?</[^>]+>', "", s, flags=re.S | re.I)
        elif sel.startswith("."):
            sel_re = re.escape(sel[1:])
            s = re.sub(rf'<[^>]*class=["\'][^"\']*{sel_re}[^"\']*["\'][^>]*>.*?</[^>]+>', "", s, flags=re.S | re.I)

    # 3) Block elements → newlines
    for tag in ("p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "section", "blockquote"):
        s = re.sub(rf"<{tag}\b[^>]*>", "\n\n", s, flags=re.I)
        s = re.sub(rf"</{tag}>", "\n", s, flags=re.I)
        s = re.sub(rf"<{tag}\b[^>]*/>", "\n", s, flags=re.I)

    # 4) Headings (placeholder for future enhancement)
    for i in range(1, 7):
        # Open/close tags already handled above; use placeholders if needed
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

    # 10) Strip all remaining HTML tags
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

    # 12) Collapse extra blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = s.strip()

    return s


if __name__ == "__main__":
    # Self-test
    sample = '''
    <p>Hello <strong>world</strong>!</p>
    <p>This is a <a href="https://example.com">link</a>.</p>
    <p><img src="https://example.com/img.jpg" alt="Test image"></p>
    <script>alert('xss')</script>
    '''
    print(html_to_markdown(sample))
