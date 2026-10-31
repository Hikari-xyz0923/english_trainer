# -*- coding: utf-8 -*-
"""登录态改动后的冒烟：①已登录正常进主页 ②未登录落到登录页且不报错。"""
import sys

sys.path.insert(0, r"C:\Users\15861\Desktop\english_trainer")
from streamlit.testing.v1 import AppTest

APP = r"C:\Users\15861\Desktop\english_trainer\app.py"

print("---- 场景 A：已登录（预设 session）----")
at = AppTest.from_file(APP, default_timeout=30)
at.session_state["user_id"] = 1
at.session_state["username"] = "smoke_test"
at.run()
print("exception:", [e.message for e in at.exception])
print("有句子分析按钮:", any("开始分析" in b.label for b in at.button))
print("有打卡按钮:", any("打卡" in b.label for b in at.button))

print("---- 场景 B：未登录（无 session、无 cookie）----")
at2 = AppTest.from_file(APP, default_timeout=30)
at2.run()
print("exception:", [e.message for e in at2.exception])
titles = [t.value for t in at2.title]
print("标题:", titles)
print("登录按钮:", [b.label for b in at2.button])
print("是否显示免登录提示:", any("30 天内" in i.value for i in at2.info))

ok = (not at.exception) and (not at2.exception) and any("🔐" in t for t in titles)
print("AUTH_SMOKE_OK" if ok else "AUTH_SMOKE_FAIL")
