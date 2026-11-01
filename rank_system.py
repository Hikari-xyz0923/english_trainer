# -*- coding: utf-8 -*-
"""段位系统：把积分换算成书虫世界的身份。
纯查表函数，不碰数据库——数据库管"存多少分"，这里管"分等于什么身份"。"""

# ---- 段位表：7 大段 × 3 小段 = 21 级 ----
# thresholds = 达到该大段所需的最低总积分（阶梯式，越往上越陡）
RANKS = [
    {"name": "🐣 书虫幼崽", "members": ["幼崽1", "幼崽2", "幼崽3"], "threshold": 0},
    {"name": "🐛 单词猎手", "members": ["猎手1", "猎手2", "猎手3"], "threshold": 100},
    {"name": "⚔️ 短句骑士", "members": ["骑士1", "骑士2", "骑士3"], "threshold": 300},
    {"name": "🗺️ 段落游侠", "members": ["游侠1", "游侠2", "游侠3"], "threshold": 600},
    {"name": "📚 篇章学者", "members": ["学者1", "学者2", "学者3"], "threshold": 1000},
    {"name": "🎩 博览大师", "members": ["大师1", "大师2", "大师3"], "threshold": 1600},
    {"name": "🐉 语感宗师", "members": ["宗师1", "宗师2", "宗师3"], "threshold": 2500},
]

# 升级仪式感文案：升入某大段时展示
RANK_UP_MESSAGES = {
    "🐛 单词猎手": "你开始主动追捕生词了——猎手时代开启！",
    "⚔️ 短句骑士": "你已经能正面迎战完整的句子了！",
    "🗺️ 段落游侠": "长段阅读不再令你心慌，游侠踏遍新领地！",
    "📚 篇章学者": "整篇英文已是你的书房。",
    "🎩 博览大师": "小说、科普、新闻——跨题材通吃！",
    "🐉 语感宗师": "你不再翻译英语，你直接懂了。",
}

def points_to_rank(points):
    """把总积分换算成段位。返回字典：
    rank_name  大段名 / sub_name 小段名 / global_level 全局等级(1~21)
    next_need  距下一小段还差多少分（宗师3封顶则返回 None）
    progress   当前大段内的小段进度提示文案"""
    # ① 先定位大段：从高到低找第一个"够得着"的门槛（表要倒着找！）
    rank_idx = 0
    for i in range(len(RANKS) - 1, -1, -1):
        if points >= RANKS[i]["threshold"]:
            rank_idx = i
            break
    rank = RANKS[rank_idx]

    # ② 在大段内定位小段：大段门槛到下一大段门槛之间均分成 3 份
    if rank_idx + 1 < len(RANKS):
        seg_end = RANKS[rank_idx + 1]["threshold"]   # 本大段"毕业分"
    else:
        seg_end = rank["threshold"] + 1200           # 宗师段：虚构一个毕业分，可自行调整
    seg_span = (seg_end - rank["threshold"]) / 3     # 每小段的宽度
    # 小段序号：0/1/2（封顶保护，防止除法浮点误差越界）
    sub_idx = min(int((points - rank["threshold"]) // seg_span), 2)

    # ③ 距下一小段还差多少分
    if sub_idx < 2:
        next_line = rank["threshold"] + seg_span * (sub_idx + 1)
        next_need = max(0, int(next_line - points) + 1)   # +1 因为要"超过"才升级
    elif rank_idx + 1 < len(RANKS):
        next_need = max(0, int(RANKS[rank_idx + 1]["threshold"] - points) + 1)
    else:
        next_need = None      # 宗师3：已封顶

    return {
        "rank_name": rank["name"],
        "sub_name": rank["members"][sub_idx],
        "global_level": rank_idx * 3 + sub_idx + 1,    # 全局等级 1~21
        "next_need": next_need,
        "progress": f"{rank['members'][sub_idx]}（{rank_idx * 3 + sub_idx + 1}/21级）",
        # ↓ 下面四个是给"成长历程"页画阶梯和进度条用的，
        #   上面的老字段一个没动，侧边栏那段代码不用改。
        "rank_index": rank_idx,                          # 第几个大段（0 起）
        "sub_index": sub_idx,                            # 大段内第几小段（0/1/2）
        "seg_start": rank["threshold"],                  # 本大段起点分
        "seg_end": seg_end,                              # 本大段终点分（=下一大段门槛）
    }