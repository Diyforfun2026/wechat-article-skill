#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章抓取 — 主入口 CLI
- 4 层降级链：captcha_check → meta_extract → curl_cffi_fetch → sogou_search
- 不依赖外部 API 服务，纯本地抓取
- Chrome headless 兜底 CSR 动态渲染
"""

from __future__ import annotations
import sys
import json
import argparse
from dataclasses import asdict, dataclass, field
from typing import Optional

# 让脚本可独立运行
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
    """统一的抓取结果"""
    success: bool
    url: str
    method: str = ""                # 成功时用的策略
    title: str = ""
    author: str = ""
    account: str = ""
    description: str = ""
    cover: str = ""
    publish_time: str = ""
    content_md: str = ""            # Markdown 正文（可能为空——CSR 限制）
    content_chars: int = 0
    error: str = ""
    fallback_urls: list = field(default_factory=list)  # sogou 搜到的转载链接
    chrome_used: bool = False       # 是否启用了 Chrome headless


def fetch_article(url: str, want_content: bool = True, timeout: int = 15, use_chrome: bool = True) -> WechatArticleResult:
    """
    抓取单篇公众号文章。
    流程：URL 标准化 → captcha 检测 → meta 提取 → 正文抓取（CSR 时启用 Chrome 兜底）→ 失败时返回 sogou 结果

    Args:
        url: 公众号文章 URL
        want_content: 是否抓正文
        timeout: curl_cffi/requests 超时
        use_chrome: 当 CSR 抓不到正文时，是否启用本机 Chrome headless 兜底
    """
    result = WechatArticleResult(success=False, url=url)

    # 1) URL 标准化
    norm_url = normalize_wechat_url(url)
    if not norm_url:
        result.error = "URL 为空"
        return result
    result.url = norm_url

    if not is_valid_wechat_article_url(norm_url):
        result.error = f"不是合法的 mp.weixin.qq.com 文章 URL: {norm_url}"
        return result

    # 2) 先用 curl_cffi/requests 抓（快、便宜）
    fetched = fetch(norm_url, timeout=timeout)
    if not fetched.success:
        # 网络层失败——直接试 Chrome
        if use_chrome and os.path.exists(CHROME_PATH):
            chrome_r = fetch_with_chrome(norm_url, timeout=timeout + 15, wait_js=2.5)
            result.chrome_used = True
            if chrome_r.success:
                fetched = FetchResult(success=True, method="chrome_headless", html=chrome_r.html, status_code=200)
            else:
                result.error = f"curl_cffi 失败 ({fetched.error})；Chrome 也失败 ({chrome_r.error})"
                return result
        else:
            result.error = f"抓取失败 ({fetched.method}): {fetched.error}"
            return result

    html = fetched.html
    result.method = fetched.method

    # 3) 验证码检测（必须先于 meta）
    if is_captcha_blocked(html):
        reason = captcha_reason(html)
        result.error = f"被微信反爬墙拦截: {reason}"

        # 优先用 Chrome 突破（captcha 墙 Chrome 有时能过）
        if use_chrome and os.path.exists(CHROME_PATH):
            chrome_r = fetch_with_chrome(norm_url, timeout=timeout + 20, wait_js=3.5)
            result.chrome_used = True
            if chrome_r.success and not is_captcha_blocked(chrome_r.html):
                html = chrome_r.html
                result.method = "chrome_headless"
                # 不 return，继续往下走 meta 提取
            else:
                # Chrome 也被拦——降级到 Sogou
                meta = extract_meta(chrome_r.html if chrome_r.success else html)
                _fill_sogou_fallbacks(result, meta.title)
                return result
        else:
            # 无 Chrome，直接降级 Sogou
            meta = extract_meta(html)
            _fill_sogou_fallbacks(result, meta.title)
            return result

    # 4) meta 提取（永远成功）
    meta = extract_meta(html)
    result.title = meta.title
    result.author = meta.author
    result.account = meta.account
    result.description = meta.description
    result.cover = meta.cover
    result.publish_time = meta.publish_time

    # 5) 正文提取
    if want_content:
        content_html = extract_main_content(html)
        content_md = ""
        if content_html and len(content_html) > 200:
            content_md = html_to_markdown(content_html, base_url=norm_url)

        # CSR 限制：正文太短/为空，启用 Chrome 兜底
        if not content_md or len(content_md) < 100:
            if use_chrome and os.path.exists(CHROME_PATH):
                chrome_r = fetch_with_chrome(norm_url, timeout=timeout + 15, wait_js=3.0)
                result.chrome_used = True
                if chrome_r.success:
                    chrome_html = chrome_r.html
                    chrome_meta = extract_meta(chrome_html)
                    # Chrome 拿到的 meta 覆盖（更准确）
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

    # 6) 判断成功标准
    if result.title or result.description:
        result.success = True
    else:
        result.error = "HTML 解析失败：无 meta、无正文"

    return result


def _fill_sogou_fallbacks(result: WechatArticleResult, title: str) -> None:
    """captcha 时的 Sogou 转载兜底"""
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
    """格式化为 Markdown 输出"""
    lines = []
    title = article.title or "未知标题"
    lines.append(f"# {title}")
    lines.append("")

    meta_lines = []
    if article.publish_time:
        meta_lines.append(f"**发布时间**: {article.publish_time}")
    if article.account:
        meta_lines.append(f"**公众号**: {article.account}")
    elif article.author:
        meta_lines.append(f"**作者**: {article.author}")
    if article.url:
        meta_lines.append(f"**原文链接**: {article.url}")
    if article.cover:
        meta_lines.append(f"**封面**: {article.cover}")
    if article.method:
        meta_lines.append(f"**抓取方式**: {article.method}")

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
        lines.append(f"> ⚠️ **抓取失败**: {article.error}")
        lines.append("")

    if article.fallback_urls:
        lines.append("")
        lines.append("## 可能的转载链接（搜狗）")
        for fb in article.fallback_urls:
            lines.append(f"- [{fb['title']}]({fb['url']})")
            if fb.get('summary'):
                lines.append(f"  - {fb['summary']}")
            if fb.get('publish_time'):
                lines.append(f"  - {fb['publish_time']}")

    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="微信公众号文章抓取")
    parser.add_argument("url", nargs="?", help="公众号文章 URL")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--no-content", action="store_true", help="不抓正文（只拿 meta）")
    parser.add_argument("--sogou", type=str, help="用标题搜 sogou（绕过 captcha 找转载）")
    parser.add_argument("--timeout", type=int, default=15, help="超时秒数")
    parser.add_argument("--no-chrome", action="store_true", help="禁用本机 Chrome headless 兜底")
    args = parser.parse_args()

    if args.sogou:
        # 纯搜索模式
        results = sogou_search(args.sogou, limit=10)
        if args.json:
            print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
        else:
            print(f"## 搜狗微信搜索: {args.sogou}")
            for r in results:
                print(f"\n### [{r.rank}] {r.title}")
                print(f"- URL: {r.url}")
                if r.summary:
                    print(f"- 摘要: {r.summary}")
                if r.publish_time:
                    print(f"- 时间: {r.publish_time}")
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
        # 移除长字段避免输出爆炸
        d = asdict(article)
        if not args.no_content and len(d.get('content_md', '')) > 500:
            d['content_md_preview'] = d['content_md'][:500] + "..."
            d['content_md'] = ""
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(article))

    # 退出码：成功 0，失败 1
    sys.exit(0 if article.success else 1)


if __name__ == "__main__":
    main()
