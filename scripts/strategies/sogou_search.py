#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strategy: Sogou WeChat Search (bypass captcha to find reposts).

- When mp.weixin.qq.com is blocked by captcha, search Sogou for reposts with the same title
- Constructs the search URL and parses the result list
"""

from __future__ import annotations
import re
from typing import Optional
from urllib.parse import quote, urlparse
from dataclasses import dataclass

SOGOU_WEIXIN = "https://weixin.sogou.com/weixin"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class SogouResult:
    rank: int
    title: str
    url: str
    summary: str
    publish_time: str


def _fetch_sogou(query: str, page: int = 1) -> str:
    """Fetch the Sogou WeChat Search results HTML."""
    try:
        from curl_cffi import requests as cffi_requests  # type: ignore
        sess = cffi_requests.Session(impersonate="chrome120")
    except ImportError:
        import requests  # type: ignore
        sess = requests.Session()

    params = {"query": query, "type": "2", "page": str(page), "ie": "utf8"}
    headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weixin.sogou.com/",
    }
    try:
        r = sess.get(SOGOU_WEIXIN, params=params, headers=headers, timeout=15)
        return r.text
    except Exception:
        return ""


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<!--red_beg-->|<!--red_end-->", "", s or "")).strip()


def search(query: str, page: int = 1, limit: int = 10) -> list[SogouResult]:
    """
    Search Sogou for WeChat Official Account articles.

    Returns a list of SogouResult (may be empty: Sogou rate-limit returns []).
    """
    html = _fetch_sogou(query, page=page)
    if not html:
        return []

    # Sogou rate-limit detection
    if re.search(r"验证码|安全验证|异常访问|访问过于频繁|请输入验证码", html):
        return []

    results: list[SogouResult] = []

    # Sogou 2024+ redesign: results are inside <div class="news-box"> in <div class="txt-box">
    # Title link format: <a target="_blank" href="/link?url=...">title</a>
    # Summary in <p> inside txt-box
    # Time in a separate <div class="s-p">

    # Key: locate the real result li (id starts with sogou_vr_ and ends with _box_)
    # Top-nav li ids are sogou_xinwen / sogou_wangye, etc., filter those out
    # Match sogou_vr li one by one, each li goes until the next li or </ul>
    sogou_vr_pat = re.compile(
        r'<li\b[^>]*\bid=["\']sogou_vr_\d+_box_\d+["\'][^>]*>(.*?)</li>',
        re.S | re.I,
    )
    news_boxes = sogou_vr_pat.findall(html)
    if not news_boxes:
        # Fallback: use txt-box directly (one per result)
        news_boxes = re.findall(
            r'<div[^>]*class=["\']txt-box["\'][^>]*>(.*?)(?=<div[^>]*class=["\']txt-box["\']|$)',
            html,
            re.S | re.I,
        )

    for i, box in enumerate(news_boxes[:limit]):
        # Find the title: permissive match — any <a href="/link?url=..."> text
        # Then check whether the entire a-tag's attrs contain _title_ or not _img_
        # Simplified: take the first non-image /link?url= link

        # Find all <a> with /link?url=
        all_links = list(re.finditer(
            r'<a\b[^>]*\bhref=["\'](/link\?url=[^"\']+)["\'][^>]*>(.*?)</a>',
            box,
            re.S | re.I,
        ))
        a_match = None
        for cand in all_links:
            tag = box[cand.start():cand.end()]
            # Skip image links (id ends with _img_ or uigs starts with article_image)
            if re.search(r'id=["\']sogou_vr_\d+_img_\d+["\']', tag):
                continue
            if 'article_image_' in tag:
                continue
            a_match = cand
            break
        if not a_match:
            continue

        url = a_match.group(1)
        title = _clean(re.sub(r"<[^>]+>", "", a_match.group(2)))
        if not title or title in ("搜狗搜索", "微信"):
            continue

        # Summary: <p> text inside txt-box
        p_match = re.search(r'<p\b[^>]*>(.*?)</p>', box, re.S | re.I)
        summary = _clean(re.sub(r"<[^>]+>", "", p_match.group(1))) if p_match else ""

        # Time: separate <div class="s-p">
        t_match = re.search(
            r'<div[^>]*class=["\']s-p["\'][^>]*>(.*?)</div>',
            box,
            re.S | re.I,
        )
        publish_time = _clean(re.sub(r"<[^>]+>", "", t_match.group(1))) if t_match else ""
        # Strip Sogou JS placeholder document.write(timeConvert('...'))
        publish_time = re.sub(r"document\.write\(timeConvert\('[\d']+'\)\)", "", publish_time).strip()

        results.append(SogouResult(
            rank=i + 1,
            title=title,
            url=url,
            summary=summary,
            publish_time=publish_time,
        ))

    return results


def resolve_sogou_url(sogou_url: str) -> Optional[str]:
    """
    Sogou search results are redirect links.

    Simplified strategy: directly constructing an mp.weixin.qq.com candidate URL is impossible
    (URL is server-side encrypted at Sogou). In real scenarios, Sogou redirect requires a
    full browser + cookies; using curl will be blocked by antispider. This function simply
    returns None, callers should fall back to "show the Sogou link for the user to click manually".
    """
    return None


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "AI programming"
    res = search(q, limit=5)
    print(f"Found {len(res)} results for {q!r}:")
    for r in res:
        print(f"  [{r.rank}] {r.title}")
        print(f"      {r.url}")
        print(f"      {r.summary[:80]}")
        print(f"      {r.publish_time}")
