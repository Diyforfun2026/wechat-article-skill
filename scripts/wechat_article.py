#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat Official Account article fetcher — main CLI entry.

- 4-tier fallback chain: captcha_check → meta_extract → curl_cffi_fetch → sogou_search
- No external API service dependency, fully local
- Chrome headless fallback for CSR dynamic rendering
"""

from __future__ import annotations
import sys
import json
import argparse
from dataclasses import asdict, dataclass, field
from typing import Optional

# Allow the script to run standalone
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from url_normalize import normalize_wechat_url, is_valid_wechat_article_url
from strategies import (
    is_captcha_blocked, captcha_reason,
    extract_meta, meta_to_dict, ArticleMeta,
    fetch, html_to_markdown, extract_main_content, FetchResult,
    search as sogou_search, resolve_sogou_url, SogouResult,
    fetch_with_chrome, ChromeFetchResult, CHROME_PATH,
)


@dataclass
class WechatArticleResult:
    """Unified fetch result."""
    success: bool
    url: str
    method: str = ""                # Strategy used on success
    title: str = ""
    author: str = ""
    account: str = ""
    description: str = ""
    cover: str = ""
    publish_time: str = ""
    content_md: str = ""            # Markdown body (may be empty — CSR limitation)
    content_chars: int = 0
    error: str = ""
    fallback_urls: list = field(default_factory=list)  # Repost links found via Sogou
    chrome_used: bool = False       # Whether Chrome headless was used


def fetch_article(url: str, want_content: bool = True, timeout: int = 15, use_chrome: bool = True) -> WechatArticleResult:
    """
    Fetch a single WeChat Official Account article.

    Flow: URL normalisation → captcha detection → meta extraction → body fetching
          (Chrome fallback when CSR-limited) → Sogou results on failure.

    Args:
        url: WeChat article URL
        want_content: Whether to fetch the body
        timeout: curl_cffi/requests timeout in seconds
        use_chrome: Whether to enable local Chrome headless when CSR returns empty body
    """
    result = WechatArticleResult(success=False, url=url)

    # 1) URL normalisation
    norm_url = normalize_wechat_url(url)
    if not norm_url:
        result.error = "URL is empty"
        return result
    result.url = norm_url

    if not is_valid_wechat_article_url(norm_url):
        result.error = f"Not a valid mp.weixin.qq.com article URL: {norm_url}"
        return result

    # 2) First try curl_cffi/requests (fast, cheap)
    fetched = fetch(norm_url, timeout=timeout)
    if not fetched.success:
        # Network-level failure — try Chrome directly
        if use_chrome and os.path.exists(CHROME_PATH):
            chrome_r = fetch_with_chrome(norm_url, timeout=timeout + 15, wait_js=2.5)
            result.chrome_used = True
            if chrome_r.success:
                fetched = FetchResult(success=True, method="chrome_headless", html=chrome_r.html, status_code=200)
            else:
                result.error = f"curl_cffi failed ({fetched.error}); Chrome also failed ({chrome_r.error})"
                return result
        else:
            result.error = f"Fetch failed ({fetched.method}): {fetched.error}"
            return result

    html = fetched.html
    result.method = fetched.method

    # 3) Captcha detection (must run before meta)
    if is_captcha_blocked(html):
        reason = captcha_reason(html)
        result.error = f"Blocked by WeChat anti-crawl wall: {reason}"

        # Prefer Chrome to bypass (Chrome sometimes passes captcha walls)
        if use_chrome and os.path.exists(CHROME_PATH):
            chrome_r = fetch_with_chrome(norm_url, timeout=timeout + 20, wait_js=3.5)
            result.chrome_used = True
            if chrome_r.success and not is_captcha_blocked(chrome_r.html):
                html = chrome_r.html
                result.method = "chrome_headless"
                # Don't return — continue to meta extraction
            else:
                # Chrome also blocked — fall back to Sogou
                meta = extract_meta(chrome_r.html if chrome_r.success else html)
                _fill_sogou_fallbacks(result, meta.title)
                return result
        else:
            # No Chrome — go straight to Sogou
            meta = extract_meta(html)
            _fill_sogou_fallbacks(result, meta.title)
            return result

    # 4) Meta extraction (always succeeds)
    meta = extract_meta(html)
    result.title = meta.title
    result.author = meta.author
    result.account = meta.account
    result.description = meta.description
    result.cover = meta.cover
    result.publish_time = meta.publish_time

    # 5) Body extraction
    if want_content:
        content_html = extract_main_content(html)
        content_md = ""
        if content_html and len(content_html) > 200:
            content_md = html_to_markdown(content_html, base_url=norm_url)

        # CSR limitation: body too short or empty, enable Chrome fallback
        if not content_md or len(content_md) < 100:
            if use_chrome and os.path.exists(CHROME_PATH):
                chrome_r = fetch_with_chrome(norm_url, timeout=timeout + 15, wait_js=3.0)
                result.chrome_used = True
                if chrome_r.success:
                    chrome_html = chrome_r.html
                    chrome_meta = extract_meta(chrome_html)
                    # Chrome-obtained meta overrides (more accurate)
                    if chrome_meta.title:
                        result.title = chrome_meta.title
                    if chrome_meta.author:
                        result.author = chrome_meta.author
                    if chrome_meta.account:
                        result.account = chrome_meta.account
                    if chrome_meta.description:
                        result.description = chrome_meta.description
                    if chrome_meta.cover:
                        result.cover = chrome_meta.cover
                    if chrome_meta.publish_time:
                        result.publish_time = chrome_meta.publish_time

                    chrome_content_html = extract_main_content(chrome_html)
                    if chrome_content_html and len(chrome_content_html) > 200:
                        chrome_md = html_to_markdown(chrome_content_html, base_url=norm_url)
                        if chrome_md and len(chrome_md) > 100:
                            content_md = chrome_md
                            result.method = "chrome_headless"

        result.content_md = content_md
        result.content_chars = len(content_md)

    # 6) Success criteria
    if result.title or result.description:
        result.success = True
    else:
        result.error = "HTML parse failed: no meta, no body"

    return result


def _fill_sogou_fallbacks(result: WechatArticleResult, title: str) -> None:
    """Sogou repost fallback when captcha is hit."""
    if not title:
        return
    sogou_results = sogou_search(title, limit=5)
    for sr in sogou_results:
        full_sogou = (
            f"https://weixin.sogou.com{sr.url}"
            if sr.url.startswith("/")
            else sr.url
        )
        result.fallback_urls.append({
            "title": sr.title,
            "url": full_sogou,
            "summary": sr.summary,
            "publish_time": sr.publish_time,
        })


def to_markdown(article: WechatArticleResult) -> str:
    """Format as Markdown output."""
    lines = []
    title = article.title or "Unknown Title"
    lines.append(f"# {title}")
    lines.append("")

    meta_lines = []
    if article.publish_time:
        meta_lines.append(f"**Publish Time**: {article.publish_time}")
    if article.account:
        meta_lines.append(f"**Account**: {article.account}")
    elif article.author:
        meta_lines.append(f"**Author**: {article.author}")
    if article.url:
        meta_lines.append(f"**Original Link**: {article.url}")
    if article.cover:
        meta_lines.append(f"**Cover**: {article.cover}")
    if article.method:
        meta_lines.append(f"**Method**: {article.method}")

    if meta_lines:
        lines.extend(meta_lines)
        lines.append("")
        lines.append("---")
        lines.append("")

    if article.description:
        lines.append(f"> {article.description}")
        lines.append("")

    if article.content_md:
        lines.append(article.content_md)
        lines.append("")

    if not article.success:
        lines.append(f"> ⚠️ **Fetch failed**: {article.error}")
        lines.append("")

    if article.fallback_urls:
        lines.append("")
        lines.append("## Possible Repost Links (Sogou)")
        for fb in article.fallback_urls:
            lines.append(f"- [{fb['title']}]({fb['url']})")
            if fb.get('summary'):
                lines.append(f"  - {fb['summary']}")
            if fb.get('publish_time'):
                lines.append(f"  - {fb['publish_time']}")

    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="WeChat Official Account article fetcher")
    parser.add_argument("url", nargs="?", help="WeChat article URL")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--no-content", action="store_true", help="Don't fetch body (meta only)")
    parser.add_argument("--sogou", type=str, help="Search Sogou by title (bypass captcha to find reposts)")
    parser.add_argument("--timeout", type=int, default=15, help="Timeout in seconds")
    parser.add_argument("--no-chrome", action="store_true", help="Disable local Chrome headless fallback")
    args = parser.parse_args()

    if args.sogou:
        # Pure search mode
        results = sogou_search(args.sogou, limit=10)
        if args.json:
            print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
        else:
            print(f"## Sogou WeChat Search: {args.sogou}")
            for r in results:
                print(f"\n### [{r.rank}] {r.title}")
                print(f"- URL: {r.url}")
                if r.summary:
                    print(f"- Summary: {r.summary}")
                if r.publish_time:
                    print(f"- Time: {r.publish_time}")
        return

    if not args.url:
        parser.print_help()
        sys.exit(1)

    article = fetch_article(
        args.url,
        want_content=not args.no_content,
        timeout=args.timeout,
        use_chrome=not args.no_chrome,
    )

    if args.json:
        # Strip long fields to avoid output blow-up
        d = asdict(article)
        if not args.no_content and len(d.get('content_md', '')) > 500:
            d['content_md_preview'] = d['content_md'][:500] + "..."
            d['content_md'] = ""
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(article))

    # Exit code: 0 on success, 1 on failure
    sys.exit(0 if article.success else 1)


if __name__ == "__main__":
    main()
