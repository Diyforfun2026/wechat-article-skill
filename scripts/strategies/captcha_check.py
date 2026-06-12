#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 0：验证码 / TCaptcha 检测
- 微信 captcha 页面返回 200 但 body 含 captcha.gtimg.com/TCaptcha.js 或 cap_appid
- 不要先试 meta 再试验证码——captcha 页面也有 og:title 但无意义
"""

from __future__ import annotations
import re

CAPTCHA_MARKERS = [
    # 真正 captcha 的强信号（精确匹配，避免误判）
    re.compile(r'captcha\.gtimg\.com/TCaptcha\.js', re.I),  # 腾讯 TCaptcha 容器
    re.compile(r'cap_appid\s*[:=]\s*["\']?\d{6,}', re.I),     # captcha 配置（6位+数字ID）
    re.compile(r'window\.cgiData\s*=\s*\{[^}]*cap_appid', re.I | re.S),  # cgiData 里含 cap_appid
    re.compile(r'<div[^>]*id=["\']verify-captcha["\']', re.I),  # captcha 容器 div
    # 弱信号（容易误判，保留作 fallback）
    re.compile(r'环境异常.*?请输入验证码', re.I | re.S),       # 完整短语（避免单独"环境异常"误判）
    re.compile(r'请输入验证码', re.I),                          # 需手动输入
    re.compile(r'访问过于频繁', re.I),                          # 频次风控
    re.compile(r'异常访问.*?请稍后', re.I | re.S),              # 完整短语
]


def is_captcha_blocked(html: str) -> bool:
    """检查 HTML 是否被微信 TCaptcha 拦截"""
    if not html:
        return False
    # TCaptcha 的几个标志
    for marker in CAPTCHA_MARKERS:
        if marker.search(html):
            return True
    return False


def captcha_reason(html: str) -> str:
    """返回被拦的原因（便于上层提示）"""
    if not html:
        return "空响应"
    if re.search(r'window\.cgiData\s*=\s*\{[^}]*cap_appid', html, re.I | re.S):
        return "TCaptcha 验证码墙（cap_appid 触发）"
    if re.search(r'cap_appid\s*[:=]\s*["\']?\d{6,}', html, re.I):
        return "TCaptcha 配置（cap_appid 触发）"
    if re.search(r'captcha\.gtimg\.com/TCaptcha\.js', html, re.I):
        return "TCaptcha JS 加载"
    if re.search(r'环境异常.*?请输入验证码', html, re.I | re.S):
        return '"环境异常"反爬墙'
    if re.search(r'请输入验证码', html):
        return "需要输入验证码"
    if re.search(r'访问过于频繁', html):
        return "访问频率触发风控"
    if re.search(r'异常访问.*?请稍后', html, re.I | re.S):
        return "异常访问触发风控"
    return "未知验证码"
