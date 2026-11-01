# -*- coding: utf-8 -*-
# ============================================================
# error_profile.py —— 个人错误画像
#
# 解决的问题：records 表里存了几十条 AI 分析，但从来没人回头看。
# 每条分析里的"🔍 中式英语错误分析"其实已经写清了错在哪，
# 缺的只是"把这些错误归类、数一数、排个序"。
#
# 做法：让模型把每条记录的错因压成 1~3 个固定类型的标签，
# 结果缓存进 error_tags 表。之后统计只是 COUNT，不再烧 API。
#
# 为什么要固定分类体系（而不是让模型自由发挥）：
#   自由发挥会得到"冠词缺失""漏冠词""冠词使用不当"三种说法各算一类，
#   统计结果变成一堆同义标签，画出来的图没有意义。
# ============================================================

import re
from collections import Counter, defaultdict

import database
import glm_api

# ---- 固定分类体系 ----
# 每一项都对应中国学习者最典型的错误，互相之间边界清楚。
# 想加类别就加在这里，别改名字（改了历史数据就断档）。
ERROR_TYPES = [
    "冠词",
    "介词",
    "时态与动词形式",
    "主谓一致与单复数",
    "词性误用",
    "中式直译",
    "搭配不当",
    "语序",
    "程度与比较",
    "其他",
]

# 类型 → 一句话解释（界面展开时用）
TYPE_HINTS = {
    "冠词": "a / an / the 该有的时候没有，不该有的时候加了",
    "介词": "listen music 这类介词该配没配、配错了",
    "时态与动词形式": "时态用错，或者动词该用 to do / doing 却用了原形",
    "主谓一致与单复数": "He go、many book 这类主语谓语或名词数对不上",
    "词性误用": "名词当动词用、形容词当副词用",
    "中式直译": "按中文语序和搭配逐字翻过来，语法没错但英语不这么说",
    "搭配不当": "词本身认识，但和它搭配的那个词用错了",
    "语序": "状语位置、疑问句语序、定语位置不对",
    "程度与比较": "very + 动词、more better 这类程度副词和比较级的问题",
    "其他": "上面九类都套不进去的",
}

CLASSIFY_PROMPT = """你是英语错误标注员。我会给你若干条中国学生的练习记录，每条包含：
  · 学生写的原句
  · 导师给出的错误分析

请为每一条挑出 1~3 个错误类型标签。**只能从下面这个固定列表里选，不许自创新词。**
每条后面是判据，请严格按判据归类——同类错误被归到不同标签，统计就没有意义了：

冠词 —— a / an / the 该有却没有，或不该有却加了
介词 —— 该有的介词缺失、或配错了（listen music 缺 to；depend of 应 depend on）
时态与动词形式 —— 时态用错；动词该用 to do / doing / 原形时选错了
  （want go → 归这里，不归词性误用；like play → 归这里）
主谓一致与单复数 —— He go、many book 这类主谓或名词单复数对不上
词性误用 —— 名词当动词、形容词当副词（* He successed；* speak English good）
  （注意：very 直接修饰动词属于「程度与比较」，不要归到这里）
中式直译 —— 按中文语序和搭配逐字翻过来，语法没大错但英语不这么说
  （「有」翻成 have 而不是 there be，归这里）
搭配不当 —— 词本身没错，但和它搭配的那个词用错了（* make a mistake 写成 do a mistake）
语序 —— 状语位置、定语位置、疑问句语序不对
程度与比较 —— very + 动词、more better、程度副词位置、比较级本身用错
其他 —— 上面九类都不是（包括学生只打了「好」这类无实质内容的输入）

输出格式（每行一条，一条记录一行，顺序和输入完全一致，不要写别的任何内容）：

序号|标签1,标签2|一句话说明错在哪（15 字以内）

示例：
3|介词,中式直译|listen music 缺 to
4|冠词|泛指单数名词前漏了 a
5|时态与动词形式|want 后要接 to go

要求：
- 标签之间用英文逗号分隔，不要空格
- 一句话说明必须具体到那句话，不要写"存在语法错误"这种空话
- 一条记录最多 3 个标签，宁可少标也不要凑数
- 不要输出 markdown 代码块，不要输出表头"""


def _extract_error_part(analysis_text):
    """从完整的 AI 分析里只取出"错误分析"那段，别把五个板块全塞给模型。
    输入短了，一次能批更多条，也更省 token。"""
    m = re.search(r"🔍\s*中式英语错误分析(.*?)(?=🧠|📈|✏️|$)", analysis_text, re.S)
    body = m.group(1) if m else analysis_text
    return body.strip()[:400]


def _parse_lines(raw, expected_ids):
    """解析模型输出。expected_ids 是本次发送的记录 id 列表，
    模型回的第 n 行对应第 n 条。"""
    result = []
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        if idx >= len(expected_ids):
            break
        parts = line.split("|")
        if len(parts) < 2:
            continue
        raw_tags = parts[1]
        note = parts[2].strip() if len(parts) > 2 else ""
        tags = [t.strip() for t in re.split(r"[,，]", raw_tags) if t.strip()]
        # 只保留白名单里的标签——模型偶尔会自作主张加"语法""用词"这种词
        tags = [t for t in tags if t in ERROR_TYPES][:3]
        if not tags:
            continue
        result.append((expected_ids[idx], ",".join(tags), note))
    return result


def classify_pending(user_id, batch_size=15, max_batches=8):
    """把所有没归类的记录分批归类，返回 (成功条数, 失败批次说明)。

    max_batches 是护栏：记录上千条时别让人点一次按钮卡十分钟。
    没归完就下次再点，进度是累加的（已归类的不会重做）。
    """
    done, errors = 0, []
    for _ in range(max_batches):
        rows = database.get_untagged_records(user_id, limit=batch_size)
        if not rows:
            break

        blocks = []
        for rid, input_text, analysis_text, created_at in rows:
            blocks.append(
                f"序号 {rid}\n原句：{input_text.strip()[:200]}\n"
                f"错误分析：{_extract_error_part(analysis_text)}"
            )
        payload_text = "\n\n".join(blocks)
        ids = [r[0] for r in rows]

        try:
            raw = glm_api.chat(CLASSIFY_PROMPT, payload_text, temperature=0.2)
            items = _parse_lines(raw, ids)
            if not items:
                # 一条都没解析出来，说明模型这次的输出格式不对，别死循环
                errors.append(f"第 {ids[0]}~{ids[-1]} 条的回复格式无法解析，已跳过")
                break
            database.save_error_tags(user_id, items)
            done += len(items)
        except Exception as e:
            errors.append(str(e)[:120])
            break

    return done, errors


def build_profile(user_id):
    """统计画像。返回字典，界面直接取用。

    口径说明（界面也要写清楚）：统计的是「命中次数」不是「记录数」——
    一条记录可能同时有介词和冠词两个错误，两类各自 +1。
    所以各类占比加起来是 100%，但总和不等于"有错误的记录数"。
    """
    tag_rows = database.get_error_tags(user_id)
    records = {r[0]: r for r in database.get_all_records(user_id)}

    counter = Counter()
    samples = defaultdict(list)

    for rid, tags, note in tag_rows:
        for t in [x.strip() for x in tags.split(",") if x.strip()]:
            counter[t] += 1
            if rid in records and len(samples[t]) < 3:
                samples[t].append({
                    "input": records[rid][1].strip(),
                    "note": note or "",
                    "time": records[rid][3],
                })

    total_hits = sum(counter.values())
    ranked = []
    for t, n in counter.most_common():
        ranked.append({
            "type": t,
            "count": n,
            "pct": round(n / total_hits * 100, 1) if total_hits else 0,
            "hint": TYPE_HINTS.get(t, ""),
            "samples": samples[t],
        })

    return {
        "records_total": len(records),
        "records_tagged": len(tag_rows),
        "total_hits": total_hits,
        "ranked": ranked,
        "untagged": database.count_untagged(user_id),
    }
