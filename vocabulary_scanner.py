# -*- coding: utf-8 -*-
"""覆盖率扫描器：把"读者词汇量"换算成 Zipf 门槛，再扫描文本揪出生词。
这是罗肖尼"98% 可理解输入"理论的量化实现。"""

import re
from wordfreq import zipf_frequency

# ---- 词汇量 → Zipf 门槛换算表 ----
# 逻辑：词汇量越大，你能认出的"低频词"越多，门槛就越低（能容忍更罕见的词）
# 这些数字是基于词频统计的经验近似值，够用就好，不必追求学术级精确
# ---- 词汇量 → Zipf 门槛换算表（v2：经实测校准版）----
# v1 拍脑袋定的门槛偏严（3500 词读者天花板只有 94%），
# v2 参考分级读物行业经验整体放宽约 0.3~0.4
VOCAB_THRESHOLDS = [
    (1000, 4.7),   # 1000：只认最高频核心词
    (2000, 4.1),   # 2000：入门阅读
    (4000, 3.5),   # 4000：进阶（3500 落在本档 → 门槛 3.5）
    (8000, 2.8),   # 8000：高等
    (16000, 2.2),  # 16000：接近母语阅读
]


def vocab_to_threshold(vocab_size):
    """把词汇量换算成 Zipf 门槛。
    入口先做类型安检：数据库/输入框来的可能是字符串 '3000'，强制转 int。"""
    try:
        vocab_size = int(vocab_size)   # '3000' → 3000；再兜不住就抛 ValueError
    except (ValueError, TypeError):
        vocab_size = 2000              # 实在转不动（空值/乱码）→ 按 2000 档兜底
    for size, threshold in VOCAB_THRESHOLDS:
        if vocab_size <= size:
            return threshold
    return 2.0
def get_best_score(low):
    """查一个词的 Zipf 分数，并尝试脱掉语法马甲（复数/时态）再查一次。
    取"马甲里最高分"——jars 查不到高分，但 jar 能查到，就算认识。"""
    best = zipf_frequency(low, "en")
    candidates = [low]                     # 候选马甲清单，先放原形
    # ---- 常见名词复数马甲 ----
    if low.endswith("ies"):
        candidates.append(low[:-3] + "y")      # stories → story
    if low.endswith("es"):
        candidates.append(low[:-2])            # boxes → box
    if low.endswith("s") and not low.endswith("ss"):
        candidates.append(low[:-1])            # jars → jar
    # ---- 常见动词时态马甲 ----
    if low.endswith("ing"):
        candidates.append(low[:-3])            # pounding → pound
        candidates.append(low[:-3] + "e")      # making → make
    if low.endswith("ed"):
        candidates.append(low[:-2])            # adorned → adorn
        candidates.append(low[:-1])            # confessed → confesse→fallback
        candidates.append(low[:-3] + "y")      # carried → carry
    # 逐个马甲查分，取最高
    for cand in candidates:
        s = get_best_score(low)
        if s > best:
            best = s
    return best
def find_hard_words(text, vocab_size):
    """扫描英文文本，找出超出读者词汇量门槛的生词。
    返回：[(单词, zipf分数), ...] 按分数升序（最陌生的排最前），已去重。"""
    threshold = vocab_to_threshold(vocab_size)

    # ① 切词：\b[a-zA-Z]+\b = 只取纯字母的"词"（排除数字、标点）
    words = re.findall(r"\b[a-zA-Z]+\b", text)

    seen = set()        # 用集合去重（同一个词出现 5 次只记 1 次）
    hard = []           # 生词收集篮

    for w in words:
        low = w.lower()             # 统一转小写：The 和 the 是同一个词
        if low in seen:
            continue
        seen.add(low)

        # ② 过滤：跳过专有名词（人名/地名如 Chen、Li——不该算生词）
        #    判断法：在原文里首字母大写，且不在句首也无法确认——简化处理：
        #    只要原文形态首字母大写就当专有名词跳过（会漏掉句首生词，但误报更少）
        if w[0].isupper():
            continue
        # ③ 过滤：单个字母（a/I 之外的孤零零字母多为缩写残渣）
        if len(low) < 2:
            continue

        score = zipf_frequency(low, "en")
        # ④ 判定：分数低于门槛 = 超出读者词汇量 = 生词！
        #    score 为 0 说明词表里没有（可能是极罕见词或变形词），也标为生词
        if score < threshold or score == 0:
            hard.append((low, round(score, 2)))

    # ⑤ 最陌生的排最前（分数低的在前）
    hard.sort(key=lambda pair: pair[1])
    return hard

def coverage_report(text, vocab_size):
    """生成一段完整的覆盖率体检报告。返回字典，方便界面直接取用。"""
    words = re.findall(r"\b[a-zA-Z]+\b", text)
    total = len(words)                       # 总词数
    hard = find_hard_words(text, vocab_size)
    # 覆盖率 = 认识的词占比。专有名词按"认识"算（人名不影响理解）
    # 直接算法：重复出现的生词也要计入覆盖率，所以要按"出现次数"算，不是按去重数
    hard_set = {w for w, s in hard}
    hard_hits = sum(1 for w in words if w[0].islower() and w.lower() in hard_set)
    proper_nouns = sum(1 for w in words if w[0].isupper())
    coverage = (total - hard_hits) / total * 100 if total else 0
    return {
        "total_words": total,               # 总词数
        "unique_hard": hard,                # 去重生词清单 [(词, 分数), ...]
        "hard_count": len(hard),            # 生词种数
        "hard_hits": hard_hits,             # 生词出现总次数（含重复）
        "coverage": round(coverage, 1),     # 覆盖率百分比
        "threshold": vocab_to_threshold(vocab_size),  # 本次用的门槛
    }