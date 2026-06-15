#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strategy 0: Captcha / TCaptcha detection.

- WeChat captcha pages return 200 but the body contains captcha.gtimg.com/TCaptcha.js or cap_appid
- Don't try meta before captcha — captcha pages also have og:title which is meaningless
"""

from __future__ import annotations
import re

CAPTCHA_MARKERS = [
    # Strong signals of real captcha (exact match, to avoid false positives)
    re.compile(r'captcha\.gtimg\.com/TCaptcha\.js', re.I),  # Tencent TCaptcha container
    re.compile(r'cap_appid\s*[:=]\s*["\']?\d{6,}', re.I),     # captcha config (6+ digit ID)
    re.compile(r'window\.cgiData\s*=\s*\{[^}]*cap_appid', re.I | re.S),  # cgiData containing cap_appid
    re.compile(r'<div[^>]*id=["\']verify-captcha["\']', re.I),  # captcha container div
    # Weak signals (easy to false-positive, kept as fallback)
    re.compile(r'环境异常.*?请输入验证码', re.I | re.S),       # Full phrase (avoids "环境异常" alone)
    re.compile(r'请输入验证码', re.I),                          # Requires manual input
    re.compile(r'访问过于频繁', re.I),                          # Frequency rate-limit
    re.compile(r'异常访问.*?请稍后', re.I | re.S),              # Full phrase
]


def is_captcha_blocked(html: str) -> bool:
    """Check whether the HTML is blocked by WeChat TCaptcha."""
    if not html:
        return False
    # A few TCaptcha markers
    for marker in CAPTCHA_MARKERS:
        if marker.search(html):
            return True
    return False


def captcha_reason(html: str) -> str:
    """Return a human-readable reason for being blocked (used by the upper layer for hints)."""
    if not html:
        return "Empty response"
    if re.search(r'window\.cgiData\s*=\s*\{[^}]*cap_appid', html, re.I | re.S):
        return "TCaptcha captcha wall (cap_appid triggered)"
    if re.search(r'cap_appid\s*[:=]\s*["\']?\d{6,}', html, re.I):
        return "TCaptcha config (cap_appid triggered)"
    if re.search(r'captcha\.gtimg\.com/TCaptcha\.js', html, re.I):
        return "TCaptcha JS loaded"
    if re.search(r'环境异常.*?请输入验证码', html, re.I | re.S):
        return '"Environment abnormal" anti-crawl wall'
    if re.search(r'请输入验证码', html):
        return "Captcha input required"
    if re.search(r'访问过于频繁', html):
        return "Access frequency triggered rate-limit"
    if re.search(r'异常访问.*?请稍后', html, re.I | re.S):
        return "Abnormal access triggered rate-limit"
    return "Unknown captcha"
