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
# 信号来源分四类（对照维基百科 WikiProject AI Cleanup 的《Signs of AI writing》）：
#   ① 词层面：罕见词占比（zipf 词频）、MSTTR、AI 偏爱词成簇（delve/leverage/robust…）
#   ② 句层面：句长变异系数、短句占比、三项并列（A, B, and C）、尾挂 -ing 假分析
#   ③ 篇层面：段落长度参差度、连接副词密度、破折号密度
#   ④ 反向：人类痕迹（问句、感叹、省略号、口语词）扣分
#
# 必须说清楚的一件事：破折号早期被错当成"人味"扣分，方向反了。
# 维基百科把破折号列为最可靠的单条信号之一（AI 拿它当万用连接符），
# 现在已改为独立 AI 侧信号。
# ============================================================

import re
from wordfreq import zipf_frequency

from vocabulary_scanner import get_best_score

# ------------------------------------------------------------
# 一、词表：套话短语 + AI 偏爱的单个词
#
# 依据：维基百科 WikiProject AI Cleanup 的《Signs of AI writing》
# （编辑从数百万条真实编辑里归纳出的实地清单），以及 GPTZero 等
# 工具公开的信号说明。两处都强调同一件事：**没有任何单条算证据**，
# 要成簇出现才有意义——所以下面每条都只给低权重，命中多条才累加。
#
# 这张表会随模型换代过期：新一代模型（GPT-5 之后）正在主动压制
# 这些词和破折号。表过期不代表方法错了，代表"套话"这一路本身有天花板。
#
# 每条：(正则, 在人话里的说法, 类型)  类型 phrase=短语 / word=单词
# ------------------------------------------------------------
TEMPLATE_PATTERNS = [
    # ---- 短语：整句骨架上的套话 ----
    (r"\bdelve[sd]? into\b", "delve into", "phrase"),
    (r"\b(?:plays?|played|playing) (?:a )?(?:crucial|vital|pivotal|significant|key) role\b",
     "plays a crucial role", "phrase"),
    (r"\bit is (?:important|crucial|essential) (?:to note|noting)\b", "it is important to note", "phrase"),
    (r"\bit is worth noting\b", "it is worth noting", "phrase"),
    (r"\bin today'?s (?:fast-paced|modern|digital|ever-changing) world\b",
     "in today's fast-paced world", "phrase"),
    (r"\bin an era of\b", "in an era of", "phrase"),
    (r"\ba testament to\b", "a testament to", "phrase"),
    (r"\bnavigat(?:e|ing|es|ed) the (?:complexit|challeng|intricac)", "navigate the complexities", "phrase"),
    (r"\bfoster(?:s|ed|ing)? (?:a )?(?:sense|environment|culture)", "foster a sense of", "phrase"),
    (r"\bin the realm of\b", "in the realm of", "phrase"),
    (r"\bnot only\b[^.]{0,80}\bbut also\b", "not only ... but also", "phrase"),
    (r"\bon the one hand\b[^.]{0,120}\bon the other hand\b", "on the one hand ... on the other hand", "phrase"),
    (r"\bin conclusion\b", "in conclusion", "phrase"),
    (r"\bthis (?:is|serves as) (?:a )?(?:reminder|testament|example)\b", "this serves as a reminder", "phrase"),
    (r"\bthe (?:world|landscape) of\b", "the landscape of", "phrase"),
    (r"\bsetting the stage for\b", "setting the stage for", "phrase"),
    (r"\b(?:unlock|unlocking) (?:the )?(?:potential|power)\b", "unlock the potential", "phrase"),
    (r"\bharness(?:ing)? the power\b", "harness the power", "phrase"),
    (r"\bstrik(?:e|es|ing) a balance\b", "strike a balance", "phrase"),
    (r"\bhing(?:e|es|ed|ing) on\b", "hinge on", "phrase"),
    (r"\bserv(?:e|es|ing) as (?:a|an)\b", "serve as a ...", "phrase"),
    (r"\bin the (?:digital|modern|information) age\b", "in the digital age", "phrase"),
    (r"\bprepar(?:e|es|ing) (?:students|them|us) for\b", "prepare students for", "phrase"),
    (r"\bthe allure of\b", "the allure of", "phrase"),
    # 笼统归因："支持者认为 / 反对者强调 / 专家指出"，却不说是谁。
    # 维基百科把这列成"weasel wording"：看上去有观点支撑，实际没有任何来源。
    (r"\b(?:proponents|opponents|critics|experts|observers|analysts|many people|some people)\s+"
     r"(?:argue|argues|contend|contends|maintain|maintains|suggest|suggests|believe|believes|"
     r"assert|asserts|emphasize|emphasizes|note|notes)\b",
     "笼统归因（proponents argue…）", "phrase"),
    # ---- 尾挂 -ing：事实说完再补一句"这说明/凸显了……"。
    #      维基百科把这个列为最典型的"假分析"：不增加信息，只增加姿态。
    (r",\s+(?:highlighting|underscoring|emphasizing|showcasing|reflecting|"
     r"demonstrating|illustrating|further reinforcing|solidifying|"
     r"fostering|ensuring|enabling|creating|allowing|paving|contributing|"
     r"promoting|encouraging|driving|shaping|preparing|positioning|marking)\b[^.]{0,90}",
     "尾挂 -ing 分析（…, highlighting …）", "phrase"),
]

# AI 偏爱的单个词。单独出现不算什么，3 个以上同时出现才是信号。
AI_WORDS = [
    (r"\bdelv(?:e|es|ed|ing)\b", "delve"),
    (r"\bleverag(?:e|es|ed|ing)\b", "leverage"),
    (r"\bseamless(?:ly)?\b", "seamless"),
    (r"\brobust\b", "robust"),
    (r"\bpivotal\b", "pivotal"),
    (r"\btapestry\b", "tapestry"),
    (r"\bmultifaceted\b", "multifaceted"),
    (r"\bunderscor(?:e|es|ed|ing)\b", "underscore"),
    (r"\bboast(?:s|ed|ing)?\b", "boast"),
    (r"\bgarner(?:s|ed|ing)?\b", "garner"),
    (r"\bmeticulous(?:ly)?\b", "meticulous"),
    (r"\bmyriad\b", "myriad"),
    (r"\bholistic\b", "holistic"),
    (r"\bintricate\b", "intricate"),
    (r"\bnuanced\b", "nuanced"),
    (r"\bshowcas(?:e|es|ed|ing)\b", "showcase"),
    (r"\bvibrant\b", "vibrant"),
    (r"\bprofound(?:ly)?\b", "profound"),
    (r"\bever-(?:evolving|growing|changing)\b", "ever-evolving"),
    (r"\bembark(?:s|ed|ing)?\b", "embark"),
    (r"\bbeacon of\b", "beacon of"),
]

# 合并成一张表，后面统一遍历（一处改，证据和打分同时生效）
ALL_PATTERNS = TEMPLATE_PATTERNS + [(pat, label, "word") for pat, label in AI_WORDS]

# 连接副词：AI 爱用，人写作文也用，但密度差异明显
CONNECTIVE_RE = re.compile(
    r"\b(?:furthermore|moreover|additionally|consequently|nevertheless|"
    r"nonetheless|therefore|thus|hence|subsequently|ultimately|overall)\b",
    re.I,
)

# 人类写作里常见、AI 很少用的痕迹。
# 注意：破折号**不在这里**——早期版本把它算成"人味"，方向错了。
# 维基百科《Signs of AI writing》把破折号列为最可靠的单条信号之一
# （AI 拿它当万用连接符），所以它现在单独算一条 AI 侧信号（见下）。
HUMAN_MARK_RE = re.compile(r"[?!]|\.\.\.|\b(?:kinda|gonna|ain'?t|well,|you know|I mean)\b", re.I)

# 破折号（em/en dash）与"三项并列"，都单独管
DASH_RE = re.compile(r"[—–]")
# 三项并列："A, B, and C"。写成 {1,} 是因为重复段吃掉的是前两项的逗号，
# 早期写成 {2,} 会要求"四个"——实测一条都对不上，整条信号是死的。
TRIAD_RE = re.compile(
    r"\b[A-Za-z][\w'-]*(?:,\s+[A-Za-z][\w'-]*){1,},\s+and\s+[A-Za-z][\w'-]*\b"
)

# 名词化：把动作变成抽象名词（decide → decision，distract → distraction）。
# AI 议论文特别爱这么写，因为抽象名词最"安全"、最不用给细节。
NOM_RE = re.compile(r"\b\w+(?:tion|sion|ment|ity|ance|ence|ness|ism|ship)s?\b", re.I)


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
    n_dash = len(DASH_RE.findall(text))
    dash_per_100 = n_dash / n_words * 100
    comma_per_sent = text.count(",") / max(len(sents), 1)

    # 三项并列："A, B, and C"。人也会用，但 AI 几乎每段都用
    n_triad = len(TRIAD_RE.findall(text))
    triad_per_100 = n_triad / n_words * 100

    # 名词化密度：抽象名词越密，越像"谁都能写的正确话"
    n_nom = len(NOM_RE.findall(text))
    nom_per_100 = n_nom / n_words * 100

    # ---- ⑤ 段落均匀度 ----
    para_lens = [len(word_list(p)) for p in paras if p.strip()]
    cv_para = _cv(para_lens) if len(para_lens) >= 3 else None

    # ---- ⑥ 套话命中（短语 + AI 偏爱词），带原句，方便当场核对 ----
    # 统计口径：按「命中的句子数」算，不按命中次数。
    # 一个句子里堆了三句套话，仍然只是"一句话像模板"，不该重复加分。
    #
    # 句子边界先算好，命中位置再用区间去对。早期版本是在循环里
    # 一边 find 一边比大小，结果把所有"在命中点之前"的句子全算成了命中，
    # 命中句数被放大成"命中位置前有几句话"——分会虚高，这里改成按区间归属。
    sent_spans = []
    cursor = 0
    for s in sents:
        idx = text.find(s[:20], cursor)
        if idx == -1:
            idx = text.find(s[:20])
        if idx == -1:
            continue
        sent_spans.append((idx, idx + len(s)))
        cursor = idx + len(s)

    def _sent_at(pos):
        """命中位置落在哪一句里。跨句（比如 not only...but also）取起始句。"""
        for i, (a, b) in enumerate(sent_spans):
            if a <= pos <= b:
                return i
        # 落在句间空白里：取前面最近的一句
        best = 0
        for i, (a, _) in enumerate(sent_spans):
            if a <= pos:
                best = i
        return best if sent_spans else 0

    template_hits = []
    hit_phrases = set()
    hit_sent_idx = set()
    word_labels = set()
    for pat, label, kind in ALL_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            if label in hit_phrases:
                continue
            hit_phrases.add(label)
            if kind == "word":
                word_labels.add(label)
            si = _sent_at(m.start())
            hit_sent_idx.add(si)
            ctx = sents[si] if si < len(sents) else ""
            template_hits.append({"phrase": label, "sentence": ctx[:220]})

    n_template_sent = len(hit_sent_idx)
    n_word_kinds = len(word_labels)

    # ------------------------------------------------------------
    # 四、加权打分
    # 每一条都能在界面的表格里对上，被问"为什么这个分"能指着表答
    #
    # 权重原则：单条都不足以定罪。维基百科的清单也强调"要成簇"，
    # 所以每条封顶都不高，靠多条累加才到高位。
    # ------------------------------------------------------------
    signals = []

    # 1) 套话命中：最硬的一路。1 句算风格，3 句以上基本就是模板腔
    t_score = min(n_template_sent * 13, 39)
    signals.append({
        "name": "模板化表达",
        "value": "%d 句命中（%s）" % (n_template_sent, "、".join(sorted(hit_phrases)[:3]) or "无"),
        "human_hint": "0~1 句",
        "ai_hint": "3 句以上",
        "verdict": "警惕" if n_template_sent >= 3 else ("略多" if n_template_sent == 2 else "正常"),
        "score": t_score,
    })

    # 2) AI 词簇：不看整句，只数"AI 偏爱的词"出现了几种。
    #    这条专治"不用套话但用词很 AI"的文本——新一代模型正是这样。
    w_score = min(max(n_word_kinds - 1, 0) * 5, 15)
    signals.append({
        "name": "AI 偏爱词簇（种类数）",
        "value": "%d 种（%s）" % (n_word_kinds, "、".join(sorted(word_labels)[:4]) or "无"),
        "human_hint": "0~1 种",
        "ai_hint": "3 种以上",
        "verdict": "成簇" if n_word_kinds >= 3 else ("略多" if n_word_kinds == 2 else "正常"),
        "score": w_score,
    })

    # 3) 名词化密度：AI 议论文爱把动作写成抽象名词（distract → distraction），
    #    抽象名词最安全、最不需要给细节。人写自己的事时名词化明显更少。
    nom_score = min(max(nom_per_100 - 6.0, 0) * 5, 15)
    signals.append({
        "name": "名词化密度（-tion/-ment/-ity…）",
        "value": "%.1f 处/百词（共 %d 处）" % (nom_per_100, n_nom),
        "human_hint": "3~6",
        "ai_hint": "8 以上",
        "verdict": "偏密" if nom_per_100 >= 8 else "正常",
        "score": nom_score,
    })

    # 3) 三项并列：人偶尔用，AI 几乎每段都用
    tri_score = min(max(triad_per_100 - 1.0, 0) * 8, 8)
    signals.append({
        "name": "三项并列（A, B, and C）密度",
        "value": "%.2f 处/百词（共 %d 处）" % (triad_per_100, n_triad),
        "human_hint": "≤ 1.0",
        "ai_hint": "≥ 2.0",
        "verdict": "偏多" if triad_per_100 >= 2.0 else "正常",
        "score": tri_score,
    })

    # 4) 破折号：维基百科列为最可靠的单条信号（AI 拿它当万用连接符）。
    #    但散文作者本来也用，所以权重低、门槛高，只在密度明显偏高时计分。
    d_score = min(max(dash_per_100 - 0.6, 0) * 9, 9)
    signals.append({
        "name": "破折号密度（每百词）",
        "value": "%.2f（%d 处）" % (dash_per_100, n_dash),
        "human_hint": "≤ 0.6",
        "ai_hint": "≥ 1.5",
        "verdict": "偏密" if dash_per_100 >= 1.5 else "正常",
        "score": d_score,
    })

    # 5) 句长均匀：AI 很少写 4 词的短句，人写作文会有。
    #    句数少于 4 时这条没有意义（一句话的"参差度"恒为 0），直接不计分。
    enough_sents = len(sents) >= 4
    if enough_sents and cv_sent < 0.35:
        s_score = min((0.35 - cv_sent) * 100 * 0.45, 16)
    else:
        s_score = 0.0
    signals.append({
        "name": "句长参差度（变异系数）",
        "value": "%.2f" % cv_sent,
        "human_hint": "≥ 0.45",
        "ai_hint": "≤ 0.35",
        "verdict": "偏均匀" if (enough_sents and cv_sent < 0.35) else ("句数太少，不判" if not enough_sents else "正常"),
        "score": s_score,
    })

    # 6) 短句占比：人会有 "That's it." 这类句子
    sh_score = 6 if (enough_sents and short_ratio < 6) else 0
    signals.append({
        "name": "短句（≤7 词）占比",
        "value": "%.0f%%" % short_ratio,
        "human_hint": "≥ 10%",
        "ai_hint": "≤ 5%",
        "verdict": "偏少" if (enough_sents and short_ratio < 6) else ("句数太少，不判" if not enough_sents else "正常"),
        "score": sh_score,
    })

    # 7) 罕见词占比：AI 爱堆"看起来很高级"的词
    r_score = min(max(rare_ratio - 8, 0) * 3.5, 14)
    signals.append({
        "name": "罕见词占比（Zipf < 3）",
        "value": "%.1f%%" % rare_ratio,
        "human_hint": "3%~10%",
        "ai_hint": "12% 以上",
        "verdict": "偏多" if rare_ratio > 12 else "正常",
        "score": r_score,
    })

    # 8) 连接副词密度：Moreover / Furthermore 堆起来就是模板腔
    c_score = min(max(conn_per_100 - 0.8, 0) * 8, 15)
    signals.append({
        "name": "连接副词密度（每百词）",
        "value": "%.2f" % conn_per_100,
        "human_hint": "≤ 0.8",
        "ai_hint": "≥ 1.5",
        "verdict": "偏密" if conn_per_100 > 1.5 else "正常",
        "score": c_score,
    })

    # 9) 段落等长：AI 爱写四个长度相近的段落
    if cv_para is not None:
        p_score = 6 if cv_para < 0.25 else 0
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

    # 10) 人类痕迹：扣分项。问句、感叹、省略号、口语词——AI 的议论文里很少
    h_bonus = min(n_human * 2, 12)
    signals.append({
        "name": "人类痕迹（问句/感叹/省略号/口语）",
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
            "ai_word_kinds": n_word_kinds,
            "triads": n_triad,
            "dashes": n_dash,
            "nominalizations": n_nom,
        },
        "signals": signals,
        "template_hits": template_hits[:10],
        "main_reasons": [s["name"] for s in top],
    }


# ------------------------------------------------------------
# 五、让模型做"审稿"，而不是"鉴定"（可选，慢）
#
# 为什么改掉"让它判是不是 AI 写的"：
#   实测过两次。第一次只把文本丢给它，它把满篇 "in today's fast-paced
#   world / a testament to" 判成"更像人写的"。第二次先把统计证据喂进去
#   再要结论，它跟着证据改口了——但那只能说明它会顺着证据说话，
#   不说明它判得准。
#   这不是这一家模型的问题，是有论文的：2026 年 HICSS 那篇测了 GPT-4 /
#   Claude / Gemini 判 AI 文本，默认 AI 文能认出，但把**人写的**判错的
#   比例高达 32%；而且只要在提示词里写一句"别让它看起来像 AI 写的"，
#   它自己写的东西就能反过来骗过另一个模型。
#   奥克兰大学那篇更直接：短文本（简答题）上，模型会把 AI 生成的答案
#   判得比真人写的"更像人"。
#
# 所以现在只让它干它真的擅长、且可核对的两件事：
#   ① 指认哪几句最像模板（人可以自己回头看原句，对不对当场能验）
#   ② 把那几句改成不像模板的样子（改写本身就是它的强项）
# 不再问它"这段是不是 AI 写的"。它答不准，答了也没法核对。
# ------------------------------------------------------------
SECOND_OPINION_PROMPT = """你是一位英语写作教师，任务是**审稿**，不是鉴定。

下面会给你一段文字，以及程序已算出的**可核对证据**（句长分布、套话命中、AI 偏爱词、破折号密度等）。

不要判断这段是不是 AI 写的。你没有能力做这个判断：语言模型判 AI 文本的准确率没有校准，
在短文本上经常把机器写的判得比人写的更像人。给出"更像人/更像 AI"的结论只会误导读者。

只做三件事：
1. 指认最多 3 句「最像模板/最像 AI 腔」的原句。每句后面用一句中文说明**具体**哪里像：
   是套话短语、是尾挂 -ing 的假分析、是三项并列、是词太大而信息太少，还是别的。
   如果整段都很自然，就写"没有明显模板句"，不要为了凑数硬找。
2. 挑其中一句，给出改法：原句 → 改后句。改的方向是"说人话"：删掉套话、把大词换成具体的词、
   长短句拆开，而**不是**把句子写得更高级。不要改变原意。
3. 一句话指出这段最大的毛病在**哪一层**：措辞 / 句式节奏 / 结构（每段一个意思但内容空）。

只输出这三部分，用中文，不要客套话，不要百分比，不要总结段。
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
        lines.append("命中的套话/AI 偏爱词（含所在原句）：")
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
        # 这一条是用来提醒"这套信号有天花板"的样本：
        # 新一代模型可以完全不堆套话，句子节奏也有起伏，照样是 AI 写的。
        # 它得分不会高——这不是 bug，是这一路方法的边界。
        "新一代 AI（不堆套话，节奏也不齐）": (
            "The train was late again. Mira sat on the cold platform and counted the announcements: "
            "delayed, delayed, cancelled. She had stopped being angry about it somewhere around March. "
            "Now she just brought a book. A man next to her was eating sunflower seeds and dropping "
            "the shells into a paper cup, one by one, with the patience of someone who had given up "
            "on the schedule entirely. She thought about asking him why. She did not. "
            "When the train finally came, it was almost empty, and they sat in different cars."
        ),
    }
    for name, s in SAMPLES.items():
        r = analyze(s)
        print("=" * 60)
        print(name, "->", r["score"], r["band"])
        for sig in r["signals"]:
            print("   %-26s %-22s %s" % (sig["name"], sig["value"], sig["verdict"]))
        if r["template_hits"]:
            print("   套话/词簇命中:", [h["phrase"] for h in r["template_hits"]])
