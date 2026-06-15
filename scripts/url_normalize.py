#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat Official Account article URL normalisation.

- Adapted from OpenCLI's `clis/weixin/download.js` `stripBoundaryWrapChars` + `normalizeWechatUrl`
- Python port: strip quote/angle-bracket wrapping, unescape backslash, decode HTML entities, force https
"""

from __future__ import annotations
import re
from urllib.parse import urlparse, urlunparse

# 9 common "wrapping" quote/bracket pairs (often seen when users copy from WeChat/Word/Pages)
WRAPPING_PAIRS = [
    ('"', '"'),
    ("'", "'"),
    ('\u201c', '\u201d'),  # "  "
    ('\u2018', '\u2019'),  # '  '
    ('\u300c', '\u300d'),  # 「  」
    ('\u300e', '\u300f'),  # 『  』
    ('\u201e', '\u201f'),  # „  ‟
    ('\u2039', '\u203a'),  # ‹  ›
    ('\u00ab', '\u00bb'),  # «  »
]
LEADING = {p[0] for p in WRAPPING_PAIRS} | {'<'}
TRAILING = {p[1] for p in WRAPPING_PAIRS} | {'>'}


def strip_boundary_chars(s: str) -> str:
    """Strip up to 4 layers of quote/angle-bracket wrapping on each end (does not touch inner URL chars)."""
    for _ in range(4):
        before = s
        for open_q, close_q in WRAPPING_PAIRS:
            if len(s) >= 2 and s.startswith(open_q) and s.endswith(close_q):
                s = s[len(open_q):-len(close_q)].strip()
                break
        while s and s[0] in LEADING:
            s = s[1:].lstrip()
        while s and s[-1] in TRAILING:
            s = s[:-1].rstrip()
        if s == before:
            break
    return s


def normalize_wechat_url(raw: str) -> str:
    """
    Normalise a WeChat Official Account article URL.

    Returns the normalised string; returns an empty string for empty/invalid input.
    """
    if not raw:
        return ""
    s = raw.strip()
    if not s:
        return ""

    # 1) Strip wrapping
    s = strip_boundary_chars(s)

    # 2) Unescape backslashes
    s = re.sub(r'\\+([:/&?=#%])', r'\1', s)

    # 3) Decode HTML entities
    s = (
        s.replace('&amp;', '&')
         .replace('&lt;', '<')
         .replace('&gt;', '>')
         .replace('&quot;', '"')
    )

    # 4) Allow bare hostname
    if s.startswith('mp.weixin.qq.com/') or s.startswith('//mp.weixin.qq.com/'):
        s = 'https://' + s.lstrip('/')

    # 5) Force https
    try:
        p = urlparse(s)
        if p.scheme in ('http', 'https') and p.hostname and p.hostname.lower() == 'mp.weixin.qq.com':
            p = p._replace(scheme='https')
            s = urlunparse(p)
    except Exception:
        pass

    return s


def is_valid_wechat_article_url(url: str) -> bool:
    """Check whether the URL is a valid mp.weixin.qq.com article URL."""
    if not url:
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.hostname != 'mp.weixin.qq.com':
        return False
    # Article short-link format /s/xxx or with ?__biz=...&mid=...
    if '/s/' in p.path or '__biz=' in p.query:
        return True
    return False


if __name__ == "__main__":
    # Simple self-test
    test_cases = [
        '"https://mp.weixin.qq.com/s/abc123"',
        "“https://mp.weixin.qq.com/s/abc123”",
        '<https://mp.weixin.qq.com/s/abc123>',
        'mp.weixin.qq.com/s/abc123',
        'https://mp.weixin.qq.com/s/abc123?__biz=xxx',
        'https://example.com/foo',
        '',
    ]
    for raw in test_cases:
        n = normalize_wechat_url(raw)
        ok = is_valid_wechat_article_url(n) if n else False
        print(f"  {raw!r:55} -> {n!r:50} valid={ok}")
