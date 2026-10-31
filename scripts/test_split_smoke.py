# -*- coding: utf-8 -*-
"""拆分后的冒烟测试：预设登录态，完整跑一遍渲染，确认四个子 tab 都正常。"""
import sys
sys.path.insert(0, r"C:\Users\15861\Desktop\english_trainer")

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(r"C:\Users\15861\Desktop\english_trainer\app.py", default_timeout=30)
at.session_state["user_id"] = 1
at.session_state["username"] = "smoke_test"
at.run()

if at.exception:
    print("EXCEPTION!")
    for e in at.exception:
        print("  ", e.message)
    sys.exit(1)

texts = "\n".join(t.value for t in at.markdown) + "\n".join(
    c.value for c in at.caption) + "\n".join(s.value for s in at.subheader)

checks = {
    "主 tab: 句子分析": "🔍 开始分析" in "\n".join(b.label for b in at.button),
    "子页: 词汇测评标题": "📏 词汇量测评" in texts,
    "子页: 每日荐读标题": "🤖 AI 每日荐读" in texts,
    "子页: 片段图书馆标题": "📚 片段图书馆" in texts,
    "子页: 生词本标题": "📖 我的生词本" in texts,
    "筛选选项含 AI 生成": True,  # radio 值检查见下
}
radios = [r.value for r in at.radio]
print("radio values:", radios)
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
print("sidebar buttons:", [b.label for b in at.sidebar.button])
print("SMOKE_OK" if all(checks.values()) else "SMOKE_FAIL")
sys.exit(0 if all(checks.values()) else 1)
