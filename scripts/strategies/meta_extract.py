#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strategy 1: Meta tag extraction (always first)
- Even when article body is inaccessible, meta tags are always readable
- Extracts: og:title, og:description, og:image, og:article:author, og:article:published_time
- Account name from <strong class="profile_meta_nickname">
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ArticleMeta:
    title: str = ""
    author: str = ""
    description: str = ""
    cover: str = ""
    publish_time: str = ""
    account: str = ""
    raw: dict = field(default_factory=dict)


# Extraction patterns (note: og:article:author uses colon-prefixed property attr)
_META_PATTERNS = {
    'title': [
        re.compile(r'<meta\s+property=[\"\']og:title[\"\']\s+content=[\"\']([^\"\']+)[\"\']', re.I),
        re.compile(r'<meta\s+name=[\"\']twitter:title[\"\']\s+content=[\"\']([^\"\']+)[\"\']', re.I),
    ],
    'author': [
        re.compile(r'<meta\s+property=[\"\']og:article:author[\"\']\s+content=[\"\']([^\"\']+)[\"\']', re.I),
        re.compile(r'<meta\s+name=[\"\']author[\"\']\s+content=[\"\']([^\"\']+)[\"\']', re.I),
    ],
    'description': [
        re.compile(r'<meta\s+property=[\"\']og:description[\"\']\s+content=[\"\']([^\"\']+)[\"\']', re.I),
        re.compile(r'<meta\s+name=[\"\']description[\"\']\s+content=[\"\']([^\"\']+)[\"\']', re.I),
    ],
    'cover': [
        re.compile(r'<meta\s+property=[\"\']og:image[\"\']\s+content=[\"\']([^\"\']+)[\"\']', re.I),
    ],
    'publish_time': [
        re.compile(r'<meta\s+property=[\"\']og:article:published_time[\"\']\s+content=[\"\']([^\"\']+)[\"\']', re.I),
        re.compile(r'<meta\s+name=[\"\']publish_time[\"\']\s+content=[\"\']([^\"\']+)[\"\']', re.I),
    ],
    'account': [
        # WeChat page: <strong class="profile_meta_nickname">xxx</strong>
        re.compile(r'<strong[^>]*class=[\"\'][^\"\']*profile_meta_nickname[^\"\']*[\"\'][^>]*>([^<]+)</strong>', re.I),
    ],
}


def _html_unescape(s: str) -> str:
    """Lightweight HTML entity decode (avoids html module dependency)"""
    return (
        s.replace('&amp;', '&')
         .replace('&lt;', '<')
         .replace('&gt;', '>')
         .replace('&quot;', '"')
         .replace('&#39;', "'")
         .replace('&nbsp;', ' ')
    )


def extract_meta(html: str) -> ArticleMeta:
    """Extract meta info from HTML (never fails -- meta is always present)"""
    meta = ArticleMeta()
    if not html:
        return meta

    for field_name, patterns in _META_PATTERNS.items():
        for p in patterns:
            m = p.search(html)
            if m:
                value = _html_unescape(m.group(1).strip())
                setattr(meta, field_name, value)
                meta.raw[field_name] = value
                break
    return meta


def meta_to_dict(meta: ArticleMeta) -> dict:
    """Convert to dict for easy JSON serialization"""
    return {
        'title': meta.title,
        'author': meta.author,
        'description': meta.description,
        'cover': meta.cover,
        'publish_time': meta.publish_time,
        'account': meta.account,
    }


if __name__ == "__main__":
    # Self-test
    sample = '''
    <html><head>
    <meta property="og:title" content="Test Article">
    <meta property="og:description" content="This is a test">
    <meta property="og:image" content="https://example.com/cover.jpg">
    <meta property="og:article:author" content="Test Author">
    <meta property="og:article:published_time" content="2026-06-10T12:00:00+08:00">
    <strong class="profile_meta_nickname">TestPub</strong>
    </head></html>
    '''
    m = extract_meta(sample)
    print(meta_to_dict(m))
