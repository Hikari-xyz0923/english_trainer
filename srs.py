# -*- coding: utf-8 -*-
"""间隔重复：决定一个生词"下次什么时候再考"。

为什么需要它
  生词本现在的状态是"收编了就躺着"。语言学习里性价比最高的单一动作，
  是"在快要忘的那天再见到一次"；而这个时间点人算不准——
  记得牢的该隔一个月，刚错的明天就该再见。所以交给算法排期。

为什么是 SM-2 的变体，不是原版
  原版只有"对/错"两档，答对就 interval *= ease。但"盯着看了十秒才想起来"
  和"秒答"显然不该排同一个间隔——前者明天就得复习，后者可以滚两个月。
  所以这里给三档：
      👎 忘了 (1)  → 重置：明天再来，间隔归 1 天
      🤔 模糊 (3)  → 间隔只拉长 1.2 倍，别让一次侥幸推得太远
      ✅ 记得 (5)  → 用完整的 ease 倍率（第一次 1 天 → 第二次 6 天 → 之后翻倍）
  其余照抄 SM-2：ease 按公式调整、下限 1.3、间隔用"调整前"的 ease 计算。

这个文件是纯函数，不碰数据库也不碰界面——所以能被单独跑测试验证。
"""

import datetime

MIN_EASE = 1.3          # ease 下限。低于它的话间隔会退化成"每天都来"，不如直接重置
MAX_INTERVAL = 365      # 间隔上限。一年一次已经等于"记住了"，没必要排更远

# 三档评分的分值（SM-2 原始量表 0~5，这里只用三个点）
QUALITY_FORGOT = 1
QUALITY_VAGUE = 3
QUALITY_GOOD = 5


def review(ease, interval, reps, lapses, quality, today=None):
    """吃进一个词的当前状态和这次的表现，吐出它的新状态。

    参数
        ease     难度因子（2.5 起步，越难越低，下限 1.3）
        interval 当前间隔（天）
        reps     连续答对次数（忘了会归零）
        lapses   累计忘了几次
        quality  这次表现：1 忘了 / 3 模糊 / 5 记得
        today    基准日期（默认今天；测试时可传固定日期）

    返回 (ease, interval, reps, lapses, due_date)
    """
    today = today or datetime.date.today()
    quality = max(0, min(5, int(quality)))

    # 老数据可能存着 NULL，兜底成新词状态
    ease = float(ease) if ease else 2.5
    interval = int(interval) if interval else 0
    reps = int(reps) if reps else 0
    lapses = int(lapses) if lapses else 0

    if quality < QUALITY_VAGUE:
        # ---- 忘了：从头再来 ----
        new_ease = ease - 0.54          # SM-2 里 q=1 时的标准扣减
        new_interval = 1
        new_reps = 0
        new_lapses = lapses + 1

    elif quality < QUALITY_GOOD:
        # ---- 模糊：算通过，但间隔只拉长 1.2 倍 ----
        new_ease = ease - 0.14          # SM-2 里 q=3 时的标准扣减
        if reps == 0:
            new_interval = 1            # 第一次见，模糊也只给 1 天
        elif reps == 1:
            new_interval = 3            # 原版这里直接给 6 天，太乐观
        else:
            new_interval = max(1, round(interval * 1.2))
        new_reps = reps + 1
        new_lapses = lapses

    else:
        # ---- 记得：SM-2 原版的阶梯 1 → 6 → interval × ease ----
        new_ease = ease + 0.1
        if reps == 0:
            new_interval = 1
        elif reps == 1:
            new_interval = 6
        else:
            # 注意用"调整前"的 ease：SM-2 原版就是这个顺序
            new_interval = max(1, round(interval * ease))
        new_reps = reps + 1
        new_lapses = lapses

    new_ease = max(MIN_EASE, round(new_ease, 2))
    new_interval = max(1, min(new_interval, MAX_INTERVAL))
    due = today + datetime.timedelta(days=new_interval)

    return new_ease, new_interval, new_reps, new_lapses, due


def is_due(due_date, today=None):
    """这个词今天该不该复习。

    due_date 为 None 表示"从没复习过的新词"，一律算到期——
    否则新收编的词永远不会出现在复习队列里。
    """
    today = today or datetime.date.today()
    if not due_date:
        return True
    if isinstance(due_date, str):
        return due_date <= today.isoformat()
    return due_date <= today


def human_interval(days):
    """把天数说成人话：1 天 / 6 天 / 3 周 / 2 个月。"""
    days = int(days)
    if days <= 1:
        return "明天"
    if days < 14:
        return f"{days} 天后"
    if days < 60:
        return f"{round(days / 7)} 周后"
    if days < 365:
        return f"{round(days / 30)} 个月后"
    return "一年后"


def stage_label(reps, interval):
    """给生词一个可读的阶段名，用来在界面上分类统计。

    阈值是经验值：间隔能撑到 21 天以上，基本算过了遗忘曲线最陡的那段。
    """
    if reps == 0:
        return "新词"
    if interval >= 21:
        return "已掌握"
    return "学习中"
