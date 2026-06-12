#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略：搜狗微信搜索（绕过 captcha 找转载）
- 当 mp.weixin.qq.com 被 captcha 挡时，通过 Sogou 找同标题转载页
- 构造搜索 URL + 解析结果列表
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
    """获取搜狗微信搜索结果 HTML"""
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
    搜狗微信搜索公众号文章。
    返回 SogouResult 列表（可能为空：被 Sogou 风控时返回 []）。
    """
    html = _fetch_sogou(query, page=page)
    if not html:
        return []

    # Sogou 风控
    if re.search(r"验证码|安全验证|异常访问|访问过于频繁|请输入验证码", html):
        return []

    results: list[SogouResult] = []

    # Sogou 2024+ 改版：结果在 <div class="news-box"> 内的 <div class="txt-box"> 里
    # 标题链接格式：<a target="_blank" href="/link?url=...">标题</a>
    # 摘要在 txt-box 内的 <p> 标签
    # 时间在独立的 <div class="s-p">

    # 关键：定位真正的结果 li（id 以 sogou_vr_ 开头 + _box_ 结尾的）
    # 顶部导航 li id 是 sogou_xinwen / sogou_wangye 等，过滤掉
    # 直接逐个匹配 sogou_vr li，每个 li 抓到下一个 li 或 </ul>
    sogou_vr_pat = re.compile(
        r'<li\b[^>]*\bid=["\']sogou_vr_\d+_box_\d+["\'][^>]*>(.*?)</li>',
        re.S | re.I,
    )
    news_boxes = sogou_vr_pat.findall(html)
    if not news_boxes:
        # 兜底：直接用 txt-box（每条结果一个）
        news_boxes = re.findall(
            r'<div[^>]*class=["\']txt-box["\'][^>]*>(.*?)(?=<div[^>]*class=["\']txt-box["\']|$)',
            html,
            re.S | re.I,
        )

    for i, box in enumerate(news_boxes[:limit]):
        # 找标题：宽松匹配——任何 <a href="/link?url=..."> 文本
        # 然后看整个 a 标签的 attrs 是不是含 _title_ 或不含 _img_
        # 简化：直接拿第一个非图片的 /link?url= 链接

        # 找出所有 /link?url= 的 <a>
        all_links = list(re.finditer(
            r'<a\b[^>]*\bhref=["\'](/link\?url=[^"\']+)["\'][^>]*>(.*?)</a>',
            box,
            re.S | re.I,
        ))
        a_match = None
        for cand in all_links:
            tag = box[cand.start():cand.end()]
            # 跳过图片链接（id 以 _img_ 结尾或 uigs 以 article_image 开头）
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

        # 摘要：txt-box 内的 <p> 文本
        p_match = re.search(r'<p\b[^>]*>(.*?)</p>', box, re.S | re.I)
        summary = _clean(re.sub(r"<[^>]+>", "", p_match.group(1))) if p_match else ""

        # 时间：独立的 <div class="s-p">
        t_match = re.search(
            r'<div[^>]*class=["\']s-p["\'][^>]*>(.*?)</div>',
            box,
            re.S | re.I,
        )
        publish_time = _clean(re.sub(r"<[^>]+>", "", t_match.group(1))) if t_match else ""
        # 去 Sogou JS 占位 document.write(timeConvert('...'))
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
    Sogou 搜索结果是跳转链接。
    简化策略：直接构造 mp.weixin.qq.com 候选 URL 不可能（URL 在 Sogou 服务端加密）。
    真实场景：Sogou 跳转需要完整浏览器+cookie，直接用 curl 会被 antispider 拦。
    本函数返回 None 即可，调用方应回退到"提供 Sogou 链接给用户手动点"。
    """
    return None


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "AI 编程"
    res = search(q, limit=5)
    print(f"Found {len(res)} results for {q!r}:")
    for r in res:
        print(f"  [{r.rank}] {r.title}")
        print(f"      {r.url}")
        print(f"      {r.summary[:80]}")
        print(f"      {r.publish_time}")
