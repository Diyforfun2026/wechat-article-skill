"""
策略包：captcha_check / meta_extract / curl_cffi_fetch / sogou_search / chrome_fetch
"""
from .captcha_check import is_captcha_blocked, captcha_reason
from .meta_extract import extract_meta, ArticleMeta, meta_to_dict
from .curl_cffi_fetch import fetch, html_to_markdown, extract_main_content, FetchResult
from .sogou_search import search, resolve_sogou_url, SogouResult
from .chrome_fetch import fetch_with_chrome, ChromeFetchResult, CHROME_PATH

__all__ = [
    "is_captcha_blocked",
    "captcha_reason",
    "extract_meta",
    "ArticleMeta",
    "meta_to_dict",
    "fetch",
    "html_to_markdown",
    "extract_main_content",
    "FetchResult",
    "search",
    "resolve_sogou_url",
    "SogouResult",
    "fetch_with_chrome",
    "ChromeFetchResult",
    "CHROME_PATH",
]
