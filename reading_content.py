# ============================================================
# reading_content.py —— 阅读营素材库：词汇测评题库 + 名著片段
# 纯数据+纯逻辑模块，没有界面（界面在 app.py 里接入）
# 版权说明：英文片段均出自"公版书"（版权已过期），可放心使用
# ============================================================

# ============================================================
# 第一部分：⚡ 快速粗测题库（20 题，娱乐级）
# 按词频分 4 层，每层 5 题：答对某层越多，词汇越够得着那一层
# 每题格式：(单词, [选项A, B, C, D], 正确答案的下标)
# ============================================================

VOCAB_QUIZ = {
    "level1": [   # 层1：最高频 2000 词
        ("improve",   ["提升", "进口", "印刷", "假装"], 0),
        ("borrow",    ["借入", "借出", "捐赠", "偷窃"], 0),
        ("decide",    ["决定", "拒绝", "装饰", "宣布"], 0),
        ("brave",     ["勇敢的", "简短的", "明亮的", "宽的"], 0),
        ("quiet",     ["安静的", "快速的", "奇怪的", "丰富的"], 0),
    ],
    "level2": [   # 层2：2000~4000
        ("acquire",     ["获得", "询问", "控告", "醒来"], 0),
        ("abandon",     ["放弃", "提高", "遵守", "吸收"], 0),
        ("eventually",  ["最终", "立刻", "偶尔", "尤其"], 0),
        ("evaluate",    ["评估", "蒸发", "升级", "强调"], 0),
        ("significant", ["重要的", "聪明地", "悄悄地", "缓慢的"], 0),
    ],
    "level3": [   # 层3：4000~8000（※ 彩蛋已修复版）
        ("vulnerable",  ["易受伤害的", "多才多艺的", "空着的", "垂直的"], 0),
        ("ambiguous",   ["模棱两可的", "雄心勃勃的", "慷慨的", "含糊其辞的"], 0),
        ("contradict",  ["反驳；与…矛盾", "控制", "贡献", "相反的"], 0),
        ("meticulous",  ["一丝不苟的", "微小的", "中间的", "疯狂的"], 0),
        ("plausible",   ["貌似合理的", "令人愉快的", "充足的", "可塑的"], 0),
    ],
    "level4": [   # 层4：8000+
        ("ubiquitous",  ["无处不在的", "犹豫不决的", "单一的", "来自宇宙的"], 0),
        ("ephemeral",   ["短暂的", "永恒的", "空灵的", "额外的"], 0),
        ("sycophant",   ["马屁精", "怀疑论者", "旁观者", "交响乐"], 0),
        ("perfunctory", ["敷衍的", "永远的", "周期性的", "完美的"], 0),
        ("obsolete",    ["过时的", "隐约的", "服从的", "吝啬的"], 0),
    ],
}


def estimate_vocab(n1, n2, n3, n4):
    """⚡粗测估分：越高的层权重越大（层1每题1分…层4每题4分），满分50
    ⚠️ 诚实声明：这是粗略估计，只用于挑选阅读材料难度，不是专业测评
    """
    score = n1 * 1 + n2 * 2 + n3 * 3 + n4 * 4
    if score <= 9:
        return "🌱 入门级", "约 2000 以内", "🌱 入门"
    elif score <= 24:
        return "🌿 初级", "约 2000 ~ 4000", "🌱 入门"
    elif score <= 39:
        return "🌳 中级", "约 4000 ~ 8000", "🌿 进阶"
    else:
        return "🏔️ 高级", "8000 以上", "🌿 进阶"


# ============================================================
# 第二部分：名著片段种子库（全部公版）
# ============================================================

PASSAGES = [
    {
        "id": 1,
        "title": "Alice's Adventures in Wonderland（爱丽丝梦游仙境）",
        "author": "Lewis Carroll · 1865",
        "level": "🌱 入门",
        "intro": "全书最著名的开场：小女孩Alice坐在河边，跟着一只兔子掉进了奇幻世界。",
        "text": (
            "Alice was beginning to get very tired of sitting by her sister on the bank, "
            "and of having nothing to do: once or twice she had peeped into the book her "
            "sister was reading, but it had no pictures or conversations in it, 'and what "
            "is the use of a book,' thought Alice, 'without pictures or conversations?' "
            "So she was considering in her own mind whether the pleasure of making a "
            "daisy-chain would be worth the trouble of getting up and picking the daisies, "
            "when suddenly a White Rabbit with pink eyes ran close by her."
        ),
        "expressions": [
            "get very tired of doing sth. —— 对做某事感到厌烦（比 be tired of 语气更生动）",
            "what is the use of ... —— ……有什么用呢（母语者最常见的自问句式）",
            "run close by —— 从身边紧挨着跑过（close by = 在近旁）",
        ],
    },
    {
        "id": 2,
        "title": "Pride and Prejudice（傲慢与偏见）",
        "author": "Jane Austen · 1813",
        "level": "🌿 进阶",
        "intro": "文学史上最著名的开头之一：一句话写尽整个时代的婚姻观，幽默中带着讽刺。",
        "text": (
            "It is a truth universally acknowledged, that a single man in possession of "
            "a good fortune, must be in want of a wife. However little known the feelings "
            "or views of such a man may be on his first entering a neighbourhood, this "
            "truth is so well fixed in the minds of the surrounding families, that he is "
            "considered as the rightful property of some one or other of their daughters."
        ),
        "expressions": [
            "in possession of —— 拥有（正式书面表达，比 have 高级）",
            "in want of —— 缺少；需要（= in need of）",
            "be fixed in one's mind —— 深深印在脑海里",
            "the rightful property of —— 名正言顺的财产（Austen 在讽刺：有钱单身汉是公共财产）",
        ],
    },
    {
        "id": 3,
        "title": "The Great Gatsby（了不起的盖茨比）",
        "author": "F. Scott Fitzgerald · 1925",
        "level": "🌳 挑战",
        "intro": "开篇父亲的忠告，奠定了全书'不动声色的叙述者'Nick 的性格底色。",
        "text": (
            "In my younger and more vulnerable years my father gave me some advice that "
            "I've been turning over in my mind ever since. 'Whenever you feel like "
            "criticizing any one,' he told me, 'just remember that all the people in this "
            "world haven't had the advantages that you've had.' He didn't say any more, "
            "but we've always been unusually communicative in a reserved way, and I "
            "understood that he meant a great deal more than that."
        ),
        "expressions": [
            "turn over in one's mind —— 在心里反复琢磨（比 think about 画面感强得多）",
            "feel like doing —— 想要做某事（口语高频表达）",
            "communicative in a reserved way —— 矜持而又坦诚（矛盾的修辞，大作家手法）",
            "mean a great deal —— 意味深长；分量很重",
        ],
    },
]


def get_passage(passage_id):
    """按编号取片段，找不到返回 None"""
    for p in PASSAGES:
        if p["id"] == passage_id:
            return p
    return None


# ---------- 独立测试区（只读）----------
if __name__ == "__main__":
    print("🧪 正在测试阅读营素材库……\n")

    total = 0
    for level_name, questions in VOCAB_QUIZ.items():
        print(f"  {level_name}: {len(questions)} 题")
        total += len(questions)
    print(f"  共 {total} 题（标准应为 20 题）\n")

    print("测试2：估算函数")
    print("  全对       →", estimate_vocab(5, 5, 5, 5))
    print("  只对层1    →", estimate_vocab(5, 0, 0, 0))
    print("  对到层3    →", estimate_vocab(5, 5, 5, 0))
    print("  全错       →", estimate_vocab(0, 0, 0, 0))

    print(f"\n测试3：共 {len(PASSAGES)} 段名著片段")
    for p in PASSAGES:
        words = len(p["text"].split())
        print(f"  #{p['id']} [{p['level']}] {p['title'][:30]}… 约 {words} 词")