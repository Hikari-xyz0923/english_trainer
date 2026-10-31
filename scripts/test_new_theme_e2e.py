# -*- coding: utf-8 -*-
"""端到端验证：AI 自由选题（不抽池），检查返回的 domain 标签。会花 token，别乱跑。"""
import sys

sys.path.insert(0, r"C:\Users\15861\Desktop\english_trainer")
import glm_api

p = glm_api.generate_library_passage(4000)
print("AI 自选领域:", p["domain"])
print("标题:", p["title"])
print("难度:", p["level"])
print("导读:", p["intro"][:60])
print("正文前 300 字:")
print(p["text"][:300])
print("...")
print("词数:", len(p["text"].split()), "| 表达数:", len(p["expressions"]))
assert p["domain"], "domain 为空"
print("E2E_OK")
