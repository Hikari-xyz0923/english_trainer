# -*- coding: utf-8 -*-
"""端到端验证：新 prompt 生成一篇「Vocaloid」主题片段，检查主题真的生效。"""
import sys

sys.path.insert(0, r"C:\Users\15861\Desktop\english_trainer")
import glm_api

p = glm_api.generate_library_passage(4000, "Vocaloid 虚拟歌手的告别演唱会")
print("标题:", p["title"])
print("风格:", p["style"] if "style" in p else "(dict 无 style 键)")
print("难度:", p["level"])
print("导读:", p["intro"][:60])
print("正文前 400 字:")
print(p["text"][:400])
print("...")
print("表达数:", len(p["expressions"]))
words = len(p["text"].split())
print("词数:", words)
low = any(k in p["text"].lower() for k in ["vocaloid", "virtual singer", "miku", "stage", "concert", "song", "music", "melody"])
print("主题相关性粗检（含音乐/演出类词）:", low)
