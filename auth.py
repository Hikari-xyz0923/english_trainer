# -*- coding: utf-8 -*-
# ============================================================
# auth.py —— 登录态持久化
#
# 【为什么需要这个文件】
#   Streamlit 的 session_state 活在一个"页面连接"里。浏览器一刷新，
#   连接就断了，session_state 整体清空，于是又弹回登录页。
#   解决办法只有一条：把"已登录"这件事记在浏览器里（cookie），
#   每次打开页面先读 cookie，验过之后再恢复登录态。
#
# 【为什么 cookie 里不直接存 user_id】
#   如果 cookie 写的是 user_id=1，那任何人打开浏览器开发者工具，
#   把它改成 2、3、4……就能冒充别人。所以这里存的是：
#        base64("user_id|用户名|过期时间") + "." + HMAC 签名
#   服务端用密钥重新算一遍签名，对不上就当作没登录。
#   改内容 → 签名对不上 → 失效，改不动。
#
# 【签名密钥从哪来】
#   优先读环境变量 / Streamlit Secrets 里的 SESSION_SECRET。
#   没配置时会用一个项目内固定串兜底（能跑，但所有部署共用同一个密钥，
#   别人拿到源码就能伪造 cookie）。想更稳：在 Secrets 里加一行
#       SESSION_SECRET=随便一串长随机字符
# ============================================================

import base64
import hashlib
import hmac
import os
import time

COOKIE_NAME = "et_auth"     # 浏览器里这个 cookie 的名字
MAX_AGE_DAYS = 30           # 记住登录多久（天）

# 没配置环境变量时的兜底密钥。生产环境请务必覆盖它。
_DEFAULT_SECRET = "english-trainer-fallback-secret-change-me"


def _secret():
    """取签名密钥：环境变量 > Streamlit Secrets > 兜底常量。"""
    s = os.environ.get("SESSION_SECRET")
    if s:
        return s.encode()
    try:
        import streamlit as st
        s = st.secrets.get("SESSION_SECRET")
    except Exception:
        s = None
    return (s or _DEFAULT_SECRET).encode()


def make_token(user_id, username):
    """生成 cookie 内容：用户信息 + 过期时间，再加签名。"""
    expires = int(time.time()) + MAX_AGE_DAYS * 86400
    payload = f"{user_id}|{username}|{expires}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    body = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{body}.{sig}"


def parse_token(token):
    """校验 cookie 内容。返回 (user_id, username)；签名错 / 过期 / 格式坏都返回 None。"""
    try:
        body, sig = token.split(".", 1)
        padded = body + "=" * (-len(body) % 4)      # base64 补齐填充位
        payload = base64.urlsafe_b64decode(padded).decode()
        user_id, username, expires = payload.rsplit("|", 2)

        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):   # 内容被改过
            return None
        if int(expires) < time.time():               # 过期了
            return None
        return int(user_id), username
    except Exception:
        return None
