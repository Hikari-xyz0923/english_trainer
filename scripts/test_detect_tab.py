# -*- coding: utf-8 -*-
"""AI 痕迹检测 tab 的渲染测试：贴一段典型 AI 文，点分析，看报告出没出来。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from streamlit.testing.v1 import AppTest

SAMPLE = (
    "The debate on whether students should be allowed to use phones during class is multifaceted. "
    "Proponents argue that phones can be a valuable educational tool, providing access to instant "
    "information and facilitating communication with teachers. This access to resources can enhance "
    "learning and prepare students for a tech-reliant world.\n\n"
    "However, opponents emphasize the distractions that phones can cause, such as social media "
    "notifications, games, and other non-educational content. They assert that phones can hinder "
    "concentration and academic performance, especially during critical learning periods.\n\n"
    "Ultimately, the decision hinges on how phones are managed. Implementing strict policies that "
    "restrict non-educational use can strike a balance, ensuring that phones serve as educational aids "
    "rather than distractions. With appropriate guidance and responsible usage, phones can indeed "
    "enhance the learning experience, fostering an environment that prepares students for the digital age."
)


def main():
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=60)
    at.session_state["user_id"] = 1
    at.session_state["username"] = "smoke_test"
    at.run()
    assert not at.exception, [e.message for e in at.exception]

    btns = [b for b in at.button if "分析痕迹" in b.label]
    if not btns:
        print("FAIL: 找不到「分析痕迹」按钮；现有按钮：", [b.label for b in at.button])
        return 1

    at.text_area(key="detect_input").set_value(SAMPLE)
    at.run()
    [b for b in at.button if "分析痕迹" in b.label][0].click()
    at.run()

    if at.exception:
        print("FAIL: 抛异常", [e.message for e in at.exception])
        return 1

    print("INFO 文案:", [c.value[:36] for c in at.caption][:3])
    dfs = at.dataframe
    if not dfs:
        print("FAIL: 没有出现信号表")
        return 1
    rows = dfs[0].value
    names = list(rows["信号"]) if hasattr(rows, "columns") else []
    print("信号条数:", len(names))
    print("信号名:", names)
    for must in ["模板化表达", "AI 偏爱词簇（种类数）", "名词化密度（-tion/-ment/-ity…）", "破折号密度（每百词）"]:
        if must not in names:
            print("FAIL: 缺少信号", must)
            return 1
    print("PASS 检测 tab 渲染正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
