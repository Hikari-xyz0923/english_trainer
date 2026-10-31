# -*- coding: utf-8 -*-
"""检测器 v2 的区分度自测。

分两类样本：
  真实生成（调 API，现场写）
  人造样本（人工写死：学生腔 / 正式 L2 议论文 / 公版文学）

目的不是"证明它准"，而是把它的边界**量出来**：
哪类会高、哪类会低、哪类必然漏。跑一次会花一点 token。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import ai_detector
from config import API_KEY, API_URL, MODEL

TOPIC = "whether students should be allowed to use phones during class"


def gen(instruction):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": instruction}],
        "temperature": 0.8,
    }
    r = requests.post(
        API_URL,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY},
        json=payload,
        timeout=90,
    )
    if r.status_code != 200:
        return "（生成失败 %d: %s）" % (r.status_code, r.text[:120])
    return r.json()["choices"][0]["message"]["content"].strip()


HUMAN_STUDENT = """I think students should not use phones in class. Last term my deskmate played games
under the desk every physics lesson. He failed the exam. But I also know phones are useful. When my
mother was ill, I needed to call home. Our school lets us keep phones in the bag. That works for me.
Maybe the rule is not the phone, it is the person. Some students can control themselves, some cannot.
I am not sure what teachers should do about it. If they take the phones away, we will find other things
to play with, right?"""

HUMAN_FORMAL_L2 = """It is widely acknowledged that the use of mobile phones in classrooms has become a
controversial issue in recent years. Proponents argue that these devices facilitate access to
educational resources and enable students to communicate with their parents in emergencies.
Opponents, on the other hand, maintain that mobile phones distract learners from academic tasks and
undermine classroom discipline. From my perspective, the merits and demerits of this phenomenon
should be examined comprehensively before any conclusion is drawn. On the one hand, strict prohibition
may be regarded as an infringement of personal freedom. On the other hand, unrestricted usage could
lead to a decline in academic performance. Therefore, it is essential for schools to formulate
reasonable regulations which balance these two considerations and ensure that students benefit from
technology without being harmed by it."""

LITERATURE = """It was the best of times, it was the worst of times, it was the age of wisdom, it was
the age of foolishness, it was the epoch of belief, it was the epoch of incredulity, it was the season
of Light, it was the season of Darkness, it was the spring of hope, it was the winter of despair, we had
everything before us, we had nothing before us, we were all going direct to Heaven, we were all going
direct the other way - in short, the period was so far like the present period, that some of its noisiest
authorities insisted on its being received, for good or for evil, in the superlative degree of comparison
only."""


def show(name, text, dump=False):
    r = ai_detector.analyze(text)
    if not r.get("ok"):
        print("%-28s -> 太短（%s 词）" % (name, r.get("n_words")))
        return name, None
    top = "、".join("%s %+d" % (s["name"][:8], s["score"]) for s in
                   sorted(r["signals"], key=lambda x: -abs(x["score"]))[:3] if s["score"] != 0)
    print("%-28s -> %3d  %-12s | %s" % (name, r["score"], r["band"], top))
    if dump:
        print("-" * 60)
        print(text)
        print("-" * 60)
        for s in r["signals"]:
            print("   %-28s %-24s %-6s %+d" % (s["name"][:26], s["value"][:22], s["verdict"], s["score"]))
    return name, r["score"]


if __name__ == "__main__":
    print("=== 人造样本 ===")
    show("学生腔（真·人写的）", HUMAN_STUDENT)
    show("正式 L2 议论文（人写的）", HUMAN_FORMAL_L2)
    show("狄更斯《双城记》（人写的）", LITERATURE)

    print("\n=== 现场生成 ===")
    a = gen("Write an essay of about 180 words on %s." % TOPIC)
    show("AI 默认腔", a, dump=True)

    b = gen("Write an essay of about 180 words on %s. Write it so it does not read like AI: "
            "avoid clichés and stock phrases, vary sentence length, use concrete details." % TOPIC)
    show("AI 被要求'别像 AI'", b, dump=True)
