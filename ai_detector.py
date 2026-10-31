# -*- coding: utf-8 -*-
# ============================================================
# ai_detector.py —— 作文「AI 痕迹」检测
#
# 设计原则（重要，别改成"一键判真假"）：
#   没有任何方法能可靠判断一段文字是不是 AI 写的。语言模型自己都做不到
#   —— 它对自己写过的东西也经常说"这不像 AI"。
#   所以这里不给"判决"，只给"痕迹清单"：
#     每一条信号都是可以当场核对的数字，界面把数字和常见区间摆出来，
#     让读者自己看哪些地方像、哪些地方不像。
#
#   这么做的另一个好处：被追问"准确率多少"时，答"我不知道准确率，
#   我给的是信号，不是分类器"——比硬报一个 92% 更站得住。
#
# 信号来源分三类：
#   ① 词层面：罕见词占比、功能词密度（zipf 词频，复用 vocabulary_scanner）
#   ② 句层面：句长变异系数、短句占比、标点习惯
#   ③ 短语层面：模板化表达命中（"delve into""plays a crucial role"…）
# ============================================================

import re
from wordfreq import zipf_frequency

from vocabulary_scanner import get_best_score

# ------------------------------------------------------------
# 一、模板短语表
# 这些是 AI 英文写作里高频出现的套话。不是"错"，是"太好认"。
# 每条：(正则, 在人话里的说法)
# ------------------------------------------------------------
TEMPLATE_PATTERNS = [
    (r"\bdelve[sd]? into\b", "delve into"),
    (r"\b(?:plays?|played|playing) (?:a )?(?:crucial|vital|pivotal|significant|key) role\b",
     "plays a crucial role"),
    (r"\bit is (?:important|crucial|essential|worth) (?:to note|noting)\b", "it is important to note"),
    (r"\bin today'?s (?:fast-paced|modern|digital|ever-changing) world\b", "in today's fast-paced world"),
    (r"\ba testament to\b", "a testament to"),
    (r"\bnavigat(?:e|ing|es|ed) the (?:complexit|challeng|intricac)", "navigate the complexities"),
    (r"\bunderscor(?:e|es|ed|ing)\b", "underscore"),
    (r"\bpivotal\b", "pivotal"),
    (r"\btapestry\b", "tapestry"),
    (r"\bmultifaceted\b", "multifaceted"),
    (r"\b(?:leverage|leveraging|leverages|leveraged)\b", "leverage"),
    (r"\bseamless(?:ly)?\b", "seamless"),
    (r"\b(?:boasts?|boasting)\b", "boast"),
    (r"\bgarner(?:s|ed|ing)?\b", "garner"),
    (r"\bfoster(?:s|ed|ing)? (?:a )?(?:sense|environment|culture)", "foster a sense of"),
    (r"\bin the realm of\b", "in the realm of"),
    (r"\bnot only\b[^.]{0,80}\bbut also\b", "not only ... but also"),
    (r"\bon the one hand\b[^.]{0,120}\bon the other hand\b", "on the one hand ... on the other hand"),
    (r"\bin conclusion\b", "in conclusion"),
    (r"\b(?:furthermore|moreover|additionally)\b", "furthermore / moreover"),
    (r"\bthis (?:is|serves as) (?:a )?(?:reminder|testament|example)\b", "this serves as a reminder"),
    (r"\bthe (?:world|landscape) of\b", "the landscape of"),
    (r"\bever-(?:evolving|growing|changing)\b", "ever-evolving"),
    (r"\b(?:unlock|unlocking) (?:the )?(?:potential|power)\b", "unlock the potential"),
    (r"\bharness(?:ing)? the power\b", "harness the power"),
]

# 连接副词：AI 爱用，人写作文也用，但密度差异明显
CONNECTIVE_RE = re.compile(
    r"\b(?:furthermore|moreover|additionally|consequently|nevertheless|"
    r"nonetheless|therefore|thus|hence|subsequently|ultimately|overall)\b",
    re.I,
)

# 人类写作里常见、AI 很少用的痕迹
HUMAN_MARK_RE = re.compile(r"[?!]|\.\.\.|—|\b(?:kinda|gonna|ain'?t|well,|you know|I mean)\b", re.I)


# ------------------------------------------------------------
# 二、基础统计
# ------------------------------------------------------------
def split_sentences(text):
    """切成句子。按 . ! ? 后跟空白切，避免把 Mr. Smith 切坏——
    简化处理：连续大写缩写（U.S.、Mr.）不切。作文场景够用。"""
    tmp = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|St|vs|etc|e\.g|i\.e)\.", r"\1<DOT>", text)
    parts = re.split(r"(?<=[.!?])[\"')\]]*\s+", tmp.strip())
    out = [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]
    return [s for s in out if re.search(r"[A-Za-z]", s)]


def word_list(text):
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)


def _cv(values):
    """变异系数 = 标准差 / 均值。衡量"参差不齐的程度"，
    比标准差本身更适合比较长短不同的文章。"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return (var ** 0.5) / mean


def _band(score):
    """分数 → 人话。档位越往上，AI 痕迹越重。"""
    if score >= 80:
        return "高度疑似 AI 生成", "🔴"
    if score >= 60:
        return "有明显 AI 痕迹", "🟠"
    if score >= 35:
        return "混合：有 AI 痕迹，也有人的痕迹", "🟡"
    return "更像人写的", "🟢"


# ------------------------------------------------------------
# 三、主分析函数
# ------------------------------------------------------------
def analyze(text):
    """输入一段英文，返回痕迹报告（字典）。

    返回结构：
        score        0~100，越大越像 AI（**是加权痕迹分，不是概率**）
        band         文字档位
        stats        基础数字（词数、句数、段落数…）
        signals      [{name, value, human_hint, ai_hint, verdict, weight, score}]
        template_hits[{phrase, sentence}]
        notes        给人看的补充说明
    """
    text = (text or "").strip()
    words = word_list(text)
    n_words = len(words)

    if n_words < 40:
        return {
            "ok": False,
            "message": "太短了，至少 40 个英文单词才能看出句长和用词分布。",
            "n_words": n_words,
        }

    sents = split_sentences(text)
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        paras = [text]

    sent_lens = [len(word_list(s)) for s in sents] or [0]
    sent_lens = [n for n in sent_lens if n > 0] or [0]

    # ---- ① 句长均匀度 ----
    cv_sent = _cv(sent_lens)
    short_ratio = sum(1 for n in sent_lens if n <= 7) / len(sent_lens) * 100

    # ---- ② 用词：罕见词与中频词 ----
    uniq = []
    seen = set()
    for w in words:
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
            uniq.append(lw)
    zipfs = [get_best_score(w) for w in uniq]
    rare_ratio = sum(1 for z in zipfs if z < 3.0) / max(len(zipfs), 1) * 100
    mid_ratio = sum(1 for z in zipfs if 3.0 <= z < 4.5) / max(len(zipfs), 1) * 100

    # 词汇多样性：每 50 词一段算 TTR 再平均（MSTTR），避免长文 TTR 天然变低
    seg = 50
    ttrs = []
    for i in range(0, n_words, seg):
        chunk = [w.lower() for w in words[i:i + seg]]
        if len(chunk) >= 20:
            ttrs.append(len(set(chunk)) / len(chunk))
    msttr = sum(ttrs) / len(ttrs) * 100 if ttrs else 0.0

    # ---- ③ 连接副词密度 ----
    n_conn = len(CONNECTIVE_RE.findall(text))
    conn_per_100 = n_conn / n_words * 100

    # ---- ④ 标点与人的痕迹 ----
    n_human = len(HUMAN_MARK_RE.findall(text))
    comma_per_sent = text.count(",") / max(len(sents), 1)

    # ---- ⑤ 段落均匀度 ----
    para_lens = [len(word_list(p)) for p in paras if p.strip()]
    cv_para = _cv(para_lens) if len(para_lens) >= 3 else None

    # ---- ⑥ 模板短语命中（带原句，方便当场核对）----
    # 统计口径：按「命中的句子数」算，不按命中次数。
    # 一个句子里堆了三句套话，仍然只是"一句话像模板"，不该重复加分。
    template_hits = []
    hit_phrases = set()
    hit_sent_idx = set()
    for pat, label in TEMPLATE_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            if label in hit_phrases:
                continue
            hit_phrases.add(label)
            # 找到命中位置所在的句子，作为证据
            pos = m.start()
            acc = 0
            ctx = ""
            for si, s in enumerate(sents):
                idx = text.find(s[:20], acc) if s else -1
                if idx <= pos and (idx != -1):
                    ctx = s
                    hit_sent_idx.add(si)
                    acc = idx + len(s)
                elif idx > pos:
                    break
            template_hits.append({"phrase": label, "sentence": ctx[:220]})

    n_template_sent = len(hit_sent_idx) if hit_sent_idx else 0

    # ------------------------------------------------------------
    # 四、加权打分
    # 每一条都能在界面的表格里对上，被问"为什么这个分"能指着表答
    # ------------------------------------------------------------
    signals = []

    # 1) 模板短语：最硬的信号。1 句算风格，3 句以上基本就是模板腔
    t_score = min(n_template_sent * 15, 45)
    signals.append({
        "name": "模板化表达",
        "value": "%d 句命中（%s）" % (n_template_sent, "、".join(sorted(hit_phrases)[:3]) or "无"),
        "human_hint": "0~1 句",
        "ai_hint": "3 句以上",
        "verdict": "警惕" if n_template_sent >= 3 else ("略多" if n_template_sent == 2 else "正常"),
        "score": t_score,
    })

    # 2) 句长均匀：AI 很少写 4 词的短句，人写作文会有
    if cv_sent < 0.35:
        s_score = min((0.35 - cv_sent) * 100 * 0.55, 19)
    else:
        s_score = 0.0
    signals.append({
        "name": "句长参差度（变异系数）",
        "value": "%.2f" % cv_sent,
        "human_hint": "≥ 0.45",
        "ai_hint": "≤ 0.35",
        "verdict": "偏均匀" if cv_sent < 0.35 else "正常",
        "score": s_score,
    })

    # 3) 短句占比：人会有 "That's it." 这类句子
    sh_score = 8 if short_ratio < 6 else 0
    signals.append({
        "name": "短句（≤7 词）占比",
        "value": "%.0f%%" % short_ratio,
        "human_hint": "≥ 10%",
        "ai_hint": "≤ 5%",
        "verdict": "偏少" if short_ratio < 6 else "正常",
        "score": sh_score,
    })

    # 4) 罕见词占比：AI 爱堆"看起来很高级"的词
    r_score = min(max(rare_ratio - 8, 0) * 4, 16)
    signals.append({
        "name": "罕见词占比（Zipf < 3）",
        "value": "%.1f%%" % rare_ratio,
        "human_hint": "3%~10%",
        "ai_hint": "12% 以上",
        "verdict": "偏多" if rare_ratio > 12 else "正常",
        "score": r_score,
    })

    # 5) 连接副词密度：Moreover / Furthermore 堆起来就是模板腔
    c_score = min(max(conn_per_100 - 0.8, 0) * 9, 18)
    signals.append({
        "name": "连接副词密度（每百词）",
        "value": "%.2f" % conn_per_100,
        "human_hint": "≤ 0.8",
        "ai_hint": "≥ 1.5",
        "verdict": "偏密" if conn_per_100 > 1.5 else "正常",
        "score": c_score,
    })

    # 6) 段落等长：AI 爱写四个长度相近的段落
    if cv_para is not None:
        p_score = 8 if cv_para < 0.25 else 0
        signals.append({
            "name": "段落长度参差度",
            "value": "%.2f（%d 段）" % (cv_para, len(para_lens)),
            "human_hint": "≥ 0.35",
            "ai_hint": "≤ 0.25",
            "verdict": "偏均匀" if cv_para < 0.25 else "正常",
            "score": p_score,
        })
    else:
        p_score = 0

    # 7) 人类痕迹：扣分项。问句、感叹、破折号、口语词——AI 的议论文里很少
    h_bonus = min(n_human * 2, 12)
    signals.append({
        "name": "人类痕迹（问句/感叹/破折号/口语）",
        "value": "%d 处" % n_human,
        "human_hint": "≥ 3 处",
        "ai_hint": "0~1 处",
        "verdict": "有人味" if n_human >= 3 else "看不出来",
        "score": -h_bonus,
    })

    raw = sum(s["score"] for s in signals)
    score = int(max(0, min(100, round(raw))))
    band, icon = _band(score)

    # 主因：分数最高的两条，面试时先说这个
    top = sorted([s for s in signals if s["score"] > 0], key=lambda x: -x["score"])[:2]

    return {
        "ok": True,
        "score": score,
        "band": band,
        "icon": icon,
        "stats": {
            "words": n_words,
            "sentences": len(sents),
            "paragraphs": len(paras),
            "avg_sent_len": round(sum(sent_lens) / len(sent_lens), 1),
            "msttr": round(msttr, 1),
            "mid_freq_ratio": round(mid_ratio, 1),
            "comma_per_sentence": round(comma_per_sent, 1),
        },
        "signals": signals,
        "template_hits": template_hits[:10],
        "main_reasons": [s["name"] for s in top],
    }


# ------------------------------------------------------------
# 五、让模型给第二意见（可选，慢）
#
# 为什么要先把统计结果喂给它：实测过，只把文本丢给模型、让它凭语感判断，
# 它会把满篇 "in today's fast-paced world / a testament to" 的文字判成
# "更像人写的"。模型对这类判断既没有校准、也不稳定。
# 所以流程反过来：程序先算、把算出来的证据摆给模型，让它复核证据，
# 而不是让它凭感觉拍一个结论。
# ------------------------------------------------------------
SECOND_OPINION_PROMPT = """你是一位英语写作教师。下面会给你一段文字，以及程序已经算出的**可核对证据**。

请严格按这个顺序做：
1. 先看证据：模板化表达命中的句数与具体短语、句长变异系数、连接副词密度。
2. 再下判断，判断必须与证据一致；如果证据和你的语感冲突，直接写"我与证据不一致"并说明原因，不要为了顺从而改口。
3. 只输出四行，不要客套话：
   判断：更像人 / 说不清 / 更像 AI
   依据：引用证据里的具体条目（例如"命中 4 句模板表达"），或原文的具体词句
   最像 AI 的一句：原句照抄；没有就写"无"
   一句话建议：如果这段要改得不像模板，最先该动哪一处

不要给百分比。你对自己写的东西都判不准，不要假装能给出精确概率。
"""


def _evidence_block(report):
    """把统计结果整理成给模型看的证据清单。"""
    if not report or not report.get("ok"):
        return "（证据缺省：文本太短，未做统计）"
    lines = ["程序统计结果：",
             "- 词数 %d，句数 %d，段落数 %d" % (
                 report["stats"]["words"], report["stats"]["sentences"], report["stats"]["paragraphs"])]
    for sig in report["signals"]:
        lines.append("- %s：%s（人写常见 %s，AI 常见 %s，判定 %s）"
                     % (sig["name"], sig["value"], sig["human_hint"], sig["ai_hint"], sig["verdict"]))
    if report["template_hits"]:
        lines.append("命中的模板化表达：")
        for h in report["template_hits"]:
            lines.append("  ・%s —— 原句：%s" % (h["phrase"], h["sentence"]))
    lines.append("综合痕迹分：%d / 100（%s）。分数是加权痕迹，不是概率。"
                 % (report["score"], report["band"]))
    return "\n".join(lines)


def second_opinion(text, report=None):
    """调模型给第二意见：先给证据，再要判断。返回 markdown 文本。
    失败时抛异常，由界面接住。"""
    import requests
    from config import API_KEY, API_URL, MODEL

    if report is None:
        report = analyze(text)

    user_content = (
        "【可核对证据】\n" + _evidence_block(report) +
        "\n\n【待判断的文字】\n" + text[:4000]
    )

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SECOND_OPINION_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }
    r = requests.post(
        API_URL,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY},
        json=payload,
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError("API 请求失败（%d）：%s" % (r.status_code, r.text[:200]))
    return r.json()["choices"][0]["message"]["content"].strip()


# ------------------------------------------------------------
# 六、独立测试区：直接运行本文件，拿内置样本跑一遍
# ------------------------------------------------------------
if __name__ == "__main__":
    SAMPLES = {
        "AI 腔（模板堆满）": (
            "In today's fast-paced world, technology plays a crucial role in shaping our daily lives. "
            "It is important to note that digital tools have become increasingly prevalent. "
            "Furthermore, these innovations delve into every aspect of society. "
            "Moreover, they serve as a testament to human creativity. "
            "Additionally, educators must navigate the complexities of modern classrooms. "
            "This underscores the pivotal importance of adaptability. "
            "In conclusion, technology is a multifaceted phenomenon that requires careful consideration."
        ),
        "学生腔（短句 + 口语 + 错误不均）": (
            "My grandmother has a small shop near the school. She sells candy and pens. "
            "I go there every day after class. Well, sometimes I just stand outside and watch her. "
            "She always says 'study hard' but she never went to school herself. "
            "That is strange, right? I think about this a lot. "
            "Last week a boy stole two pens and she did not get angry. She gave him three more. "
            "I asked why. She said he needs them more than she does."
        ),
    }
    for name, s in SAMPLES.items():
        r = analyze(s)
        print("=" * 60)
        print(name, "->", r["score"], r["band"])
        for sig in r["signals"]:
            print("   %-26s %-22s %s" % (sig["name"], sig["value"], sig["verdict"]))
        if r["template_hits"]:
            print("   模板命中:", [h["phrase"] for h in r["template_hits"]])
