#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章 URL 标准化
- 借自 OpenCLI clis/weixin/download.js 的 stripBoundaryWrapChars + normalizeWechatUrl
- Python 实现：去引号/尖括号包壳，去反斜杠转义，解 HTML entities，强制 https
"""

from __future__ import annotations
import re
from urllib.parse import urlparse, urlunparse

# 9 对常见的"包壳"引号/括号（用户从微信/Word/Pages 复制时常见）
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
    """去前后 4 层内的引号/尖括号包壳（不动 URL 内部字符）"""
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
    标准化微信公众号文章 URL。
    返回标准化后的字符串；空串/无效输入返回空串。
    """
    if not raw:
        return ""
    s = raw.strip()
    if not s:
        return ""

    # 1) 去包壳
    s = strip_boundary_chars(s)

    # 2) 去反斜杠转义
    s = re.sub(r'\\+([:/&?=#%])', r'\1', s)

    # 3) 解 HTML entities
    s = (
        s.replace('&amp;', '&')
         .replace('&lt;', '<')
         .replace('&gt;', '>')
         .replace('&quot;', '"')
    )

    # 4) 允许裸主机名
    if s.startswith('mp.weixin.qq.com/') or s.startswith('//mp.weixin.qq.com/'):
        s = 'https://' + s.lstrip('/')

    # 5) 强制 https
    try:
        p = urlparse(s)
        if p.scheme in ('http', 'https') and p.hostname and p.hostname.lower() == 'mp.weixin.qq.com':
            p = p._replace(scheme='https')
            s = urlunparse(p)
    except Exception:
        pass

    return s


def is_valid_wechat_article_url(url: str) -> bool:
    """判断是否为合法的 mp.weixin.qq.com 文章 URL"""
    if not url:
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.hostname != 'mp.weixin.qq.com':
        return False
    # 文章短链格式 /s/xxx 或带 ?__biz=...&mid=...
    if '/s/' in p.path or '__biz=' in p.query:
        return True
    return False


if __name__ == "__main__":
    # 简单自测
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
