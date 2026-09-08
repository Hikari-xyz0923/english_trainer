# ============================================================
# glm_api.py —— 核心模块：负责和智谱 GLM 服务器"打电话"
# 它不负责界面，只负责一件事：把用户输入发出去，把 AI 回答带回来
# ============================================================

import requests          # 负责发送网络请求的库（老朋友）
import streamlit as st   # ★ 挑战6新增：为了读取云端 Secrets

# 接口地址和模型名：从配置文件搬进代码里（云端读不到本地配置文件）
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash"

# ★ API Key 智能取钥匙：
#   云端环境 → 从 st.secrets 里读（部署时我们在网页上填）
#   本地环境 → 读不到 Secrets，自动退回老配置文件
try:
    API_KEY = st.secrets["API_KEY"]
except Exception:
    import config
    API_KEY = config.API_KEY


# ---------- AI 角色设定（System Prompt）----------
# 这段话相当于给 AI 的"岗位说明书"，决定了它以什么身份、什么格式回答
SYSTEM_PROMPT = """你是一位资深英语母语导师，专门帮助中国学生纠正中式英语、训练地道英语思维。

用户会发给你一句中文或中式英语，请严格按以下 5 个板块回答，不要增删板块，不要输出板块以外的内容：

✅ 地道英语表达
（给出最地道的英文说法，如有多种常用表达可列出 1~3 种）

🔍 中式英语错误分析
（逐点指出原句问题：哪里是中式直译、语法错在哪、为什么错。要具体，不许笼统。）

🧠 母语者思维逻辑
（解释英语母语者表达这个意思时的思维方式，和中文思维的差异在哪里，帮学生完成思维转换。）

📈 学术/口语词汇升级
（分两行：口语说法 2~3 个；学术/书面说法 2~3 个）

✏️ 练习造句
（出 1 道与原句主题相关的小翻译练习，另起一行给出参考答案。）
"""


# ---------- 核心函数：调用 GLM 分析用户的输入 ----------
def analyze_english(user_input):
    """
    输入：用户写的一句中文或中式英语
    输出：AI 的分析结果（一段长文本）
    出错时：抛出异常，由 app.py 捕获后弹红色错误框
    """

    # 1. 组装"对话剧本"：messages 是一个列表，按顺序装每句话
    #    - system：岗位说明书（AI 的身份）
    #    - user：用户说的话
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    # 2. 组装请求内容（payload）：告诉服务器"用哪个模型、说什么话"
    payload = {
        "model": MODEL,        # 用哪个模型
        "messages": messages,         # 对话内容
        "temperature": 0.7,           # 随机度 0~1：越高越有创意，越低越稳定
    }

    # 3. 组装请求头（headers）：
    #    "Bearer 你的Key" 就像门禁卡刷卡——向服务器证明"我是付费用户"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    # 4. 正式发请求！POST 就像"寄挂号信"，timeout=60 表示最多等 60 秒
    response = requests.post(
        API_URL,
        headers=headers,
        json=payload,       # json= 会自动把字典转成 JSON 格式发送
        timeout=60,
    )

    # 5. 检查回执：状态码 200 = 成功；其他 = 出事了（Key 错、欠费、断网……）
    if response.status_code != 200:
        raise RuntimeError(
            f"API 请求失败（状态码 {response.status_code}）：{response.text}"
        )

    # 6. 拆快递：服务器返回的是 JSON，用 .json() 转成 Python 字典
    data = response.json()

    # AI 说的话藏在 data["choices"][0]["message"]["content"] 这条路径里
    return data["choices"][0]["message"]["content"]


# ============================================================
# AI 每日荐读（★ 新增功能）
# ============================================================

READING_TUTOR_PROMPT = """你是一位精通二语习得的英语阅读教练，深受可理解输入理论影响。

用户将告诉你 ta 的词汇量。请为其生成一篇"每日精读短文"，严格满足：

1. 【难度黄金线】词汇覆盖率 ≥98%：全文约 150~1000 词，词汇量越大，内容越长。
   其中不超过2%略高于用户水平的生词（自然分布，不要集中在开头）。
2. 【内容】主题新颖有趣（科技/心理/校园/职场/旅行/科普任选其一），
   叙事为主，避免大段抽象议论。
3. 【输出格式】严格按以下结构，不要输出其他内容：

### 📄 今日短文
（英文正文，150~1000 词，一个自然段或两段均可）

### 📖 生词表
（只列出"略高难度"的词，格式：word —— 中文释义 + 英文提示句）

### 💎 地道表达
（从文中挑 3—10 个值得收编的表达：expression —— 中文解释）

### ❓ 理解自测
（2 道关于短文内容的选择题，各附 4 个选项；只给题目，答案不直接展示，
 用"参考答案：X"的格式附在每题末尾）"""


# ---------- AI 每日荐读（升级版：AI 自定主题 + 双层随机）----------

# 我们只掷"粗骰子"：10 个差异极大的领域，保证今天的文章和昨天完全不同味
READING_DOMAINS = [
    "深海或极地科考", "古代丝绸之路", "现代职场办公室", "神经科学实验室",
    "乡村学校", "职业体育更衣室", "航空航天工程", "民间传说与神话",
    "食品科学与厨房", "法律与法庭",
]

# 细骰子之一：叙事视角（决定"谁在讲故事"）
NARRATORS = [
    "第一人称亲历者", "旁观者视角", "书信/日记体", "新闻纪实风格",
]


def generate_daily_article(vocab_size):
    """
    生成每日定制文章（双层随机版）：
      第 1 层骰子：我们随机抽 1 个领域 + 1 种视角（保证跨度）
      第 2 层骰子：AI 在该领域内自由决定具体情节、人物、主题
    """
    import random
    domain = random.choice(READING_DOMAINS)
    narrator = random.choice(NARRATORS)

    messages = [
        {"role": "system", "content": READING_TUTOR_PROMPT},
        {"role": "user", "content":
            f"我的词汇量约为 {vocab_size}。"
            f"请写一篇「{domain}」领域的短文，采用{narrator}叙事。"
            f"具体写什么情节、人物、冲突，由你自由决定——"
            f"越新鲜越好，不要写俗套的故事。"},
    ]
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.9,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(f"API 请求失败（{response.status_code}）：{response.text}")

    data = response.json()
    return data["choices"][0]["message"]["content"]
# ---------- AI 片段工厂（★ 去库版：全权交给 AI 的文学素养）----------
# 设计思想：风格池/题材池是"我们有限的清单"，而模型内在的文学知识是无限的。
# 我们不再替 AI 挑作家、挑题材，只下达两个约束：
#   ① 必须是"公版作家"（版权红线，写死在指令里，不可协商）
#   ② 输出格式合约（程序要解析，不能破坏）
# 其余全部放权——每次生成的作家组合题材，由 AI 从自己的"文学史"里即兴决定。

PASSAGE_FACTORY_PROMPT = """你是英语分级阅读材料编辑，兼文学风格仿写大师。请生成一段"名著风格阅读片段"，严格满足：

1. 【作家自选】从你熟知的英语文学史中，自己挑选一位【已故超过75年、作品进入公有领域】的作家
   （如奥斯汀、狄更斯、海明威、菲茨杰拉德、马克·吐温、勃朗特姐妹、柯南·道尔、乔伊斯、伍尔夫、
    爱伦·坡、欧·亨利、杰克·伦敦等——仅举例，不必局限于此清单）。
   每次自行轮换，优先挑风格辨识度高的作家，让每次生成的风格都不同。
2. 【题材自选】情节、人物、时代背景完全由你自由创作——可以是该作家时代的经典场景，
   也可以是"如果这位作家活在今天会怎么写"的现代故事。要新鲜、不俗套。
3. 【原创铁律】必须是全新原创故事。严禁复述该作家任何真实作品的情节与原文。
4. 难度：按用户词汇量控制（3000 以下全文用最常用词；每高 2000，允许 3~4 个略难词）。
5. 长度：    正文长度要求：250～1000 个英文单词，难度越大越长。必须是一个完整的小故事
    （有开头、有转折、有结尾），不许提前收尾。
6. 输出严格按以下格式（程序要按此解析，一行都不能错、不能增删标签）：

标题：（吸引人的中英双语标题，如：深夜灯塔 The Lighthouse Keeper）
风格：（用一句话注明"本段模仿【作家名】风格原创"，如：本段模仿海明威风格原创）
难度：🌱入门 或 🌿进阶 或 🌳挑战
导读：（一句话中文导读，点出你模仿了谁的什么神韵）
正文：
（英文正文）
表达：
（3 个地道表达，每行一个，格式：expression —— 中文解释）"""


def generate_library_passage(vocab_size):
    """生成一段图书馆片段——作家与题材由 AI 自主决定（去库版）。
    返回解析好的字典；解析失败抛异常，由界面层提示重试。"""
    messages = [
        {"role": "system", "content": PASSAGE_FACTORY_PROMPT},
        {"role": "user", "content": f"读者词汇量约 {vocab_size}。请开始创作。"},
    ]
    payload = {"model": MODEL, "messages": messages, "temperature": 1.0}
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {API_KEY}"}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"API 请求失败（{response.status_code}）：{response.text}")
    raw = response.json()["choices"][0]["message"]["content"]

    # ---- 格式合约解析（原样保留，一行不改！）----
    import re
    title, level, intro, text, exprs = "", "", "", "", []
    try:
        title = re.search(r"标题：(.+)", raw).group(1).strip()
        style = re.search(r"风格：(.+)", raw).group(1).strip()   # 新增标签
        level = re.search(r"难度：(\S+)", raw).group(1).strip()
        intro = re.search(r"导读：(.+)", raw).group(1).strip()
        text = re.search(r"正文：\n(.+?)(?=\n表达：)", raw, re.DOTALL).group(1).strip()
        expr_block = re.search(r"表达：\n(.+)", raw, re.DOTALL).group(1).strip()
        exprs = [line.strip("- ").strip() for line in expr_block.split("\n") if line.strip()]
    except AttributeError:
        # 质检不通过：把 AI 的原始回复前 800 字附带在报错里，方便"抓现场"
        # raw[:800] = 只取前 800 个字符，防止刷屏
        raise RuntimeError(
            "AI 没按约定格式输出，点「生成」重试一次即可。"
            f"\n\n-------- AI 原始回复（前800字）--------\n{raw[:800]}"
        )

    if level not in ("🌱入门", "🌿进阶", "🌳挑战"):
        level = "🌿进阶"

    # 把 AI 自报的风格签名写进 intro（诚实标注：仿写非原著）
    intro = f"【{style}】{intro}"

    return {"title": title, "level": level, "intro": intro, "text": text, "expressions": exprs}


def generate_library_passage(vocab_size, domain):
    """生成一段图书馆片段，返回解析好的字典。
    解析失败会抛异常，由界面层弹错误提示。"""
    import random
        # ---- 把词汇量换算成 Zipf 门槛，让合约从"模糊叮嘱"升级为"量化条款" ----
    from vocabulary_scanner import vocab_to_threshold
    threshold = vocab_to_threshold(vocab_size)   # 安检和换算都在那个函数里做好了

    messages = [
        {"role": "system", "content": PASSAGE_FACTORY_PROMPT},
        {"role": "user", "content":
            f"读者词汇量约 {vocab_size}。请开始创作。"
            f"\n\n【难度量化条款】本文正文中，约 98% 的单词必须是日常生活中"
            f"常见的高频词（Zipf 频率分数高于 {threshold}）；"
            f"仅允许约 2% 的单词稍微罕见一些（Zipf 分数在 {threshold} 附近或略低），"
            f"这些少量生词正是读者的学习材料。"
            f"严禁大量使用 Zipf 分数低于 {threshold} 的罕见词。"
        },
    ]
    payload = {"model": MODEL, "messages": messages, "temperature": 0.9}
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {API_KEY}"}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"API 请求失败（{response.status_code}）：{response.text}")
    raw = response.json()["choices"][0]["message"]["content"]

    # ---- 解析 AI 的"半结构化"输出（按固定标签切分）----
    # 这是和 AI 协作的核心技能：约定输出格式 → 程序按格式拆解
        # ---- 分项验收版解析：每个标签独立处理，一个失败不连坐整份货 ----
    import re
    title, style, level, intro, text, exprs = "", "", "", "", "", []

    def grab(pattern, source, flags=0):
        """小工具：安全版 re.search——找到了返回内容，找不到返回空字符串"""
        m = re.search(pattern, source, flags)
        return m.group(1).strip() if m else ""

    title = grab(r"标题：\n?(.+?)(?=\n风格：|\s*风格：)", raw)
    style = grab(r"风格：\n?(.+?)(?=\n难度：|\s*难度：)", raw)
    level = grab(r"难度：\n?(\S+)", raw)
    intro = grab(r"导读：\n?(.+?)(?=\n正文：|\s*正文：)", raw)
    text  = grab(r"正文：\n?(.+?)(?=\n表达：|\s*表达：|\nexpression|\s*expression)", raw, re.DOTALL)

    # 表达部分：兼容中文「表达：」和 AI 自作主张的英文 expression 写法
    expr_block = grab(r"表达：\n?(.+)", raw, re.DOTALL)
    if not expr_block:
        # 备用方案：抓 expression 1: xxx —— xxx 这种格式
        expr_block = grab(r"expression\s*\d+[:：]\s*(.+)", raw, re.DOTALL)

    if expr_block:
        # 按 expression 或换行切分，去掉开头的编号
        exprs = [line.strip("- ").strip() for line in re.split(r"\n|expression\s*\d+[:：]", expr_block) if line.strip()]

    # 正文是灵魂——只有正文缺失才真正拒收
    if not text:
        raise RuntimeError(
            "AI 连正文都没写，点「生成」重试一次即可。"
            f"\n\n-------- AI 原始回复（前800字）--------\n{raw[:800]}"
        )

    if level not in ("🌱入门", "🌿进阶", "🌳挑战"):
        level = "🌿进阶"   # 兜底：标签异常时给中间值
    return {"title": title, "level": level, "intro": intro, "text": text, "expressions": exprs}
# ---------- 独立测试区 ----------
# if __name__ == "__main__" 的意思是：只有"直接运行本文件"时才执行下面的代码；
# 被 app.py 导入时不会执行。这样可以单独测试本模块，不影响主程序。
if __name__ == "__main__":
    print("⏳ 正在调用 GLM API 测试（约需 5~20 秒）……")
    try:
        result = analyze_english("I very like play basketball.")
        print("\n✅ 调用成功！AI 分析结果如下：\n")
        print(result)
    except Exception as e:
        print(f"\n❌ 调用失败：{e}")
# ---- 生词讲解 v2：多义项 + 词形变化 + 多例句 ----
WORD_NOTES_PROMPT = """你是一位面向中国英语学习者的词汇讲解老师。
用户会给你若干英文生词。请对每个词输出，格式必须严格遵守：

词：{英文单词}
词形：{列出常见变化形式，如复数/过去式/现在分词，用顿号隔开；没有变化的写"无变化"}
义项1：{最常用的中文释义}
义项2：{第二常用释义，没有就写"无"}
义项3：{第三常用释义，没有就写"无"}
例1：{一个最典型、最日常的英文例句}
译1：{例1的中文翻译}
例2：{另一个不同语境的英文例句}
译2：{例2的中文翻译}
例3：{第三个例句，最好能体现不同义项或搭配}
译3：{例3的中文翻译}

要求：
- 每个词一块，词与词之间用空行隔开
- 例句难度要贴近高中水平，长度 8~15 个单词
- 三个例句必须场景不同，不许换汤不换药
- 不许输出任何额外说明、开场白或总结"""

def get_word_notes(hard_words, passage_text=""):
    """为生词生成全息词卡。hard_words = [(word, zipf), ...]
    返回字典：{word: {"forms":..., "senses":[...], "examples":[(en, zh), ...]}}"""
    if not hard_words:
        return {}
    word_list = "、".join(w for w, s in hard_words)
    messages = [
        {"role": "system", "content": WORD_NOTES_PROMPT},
        {"role": "user", "content": f"请讲解以下单词：{word_list}"},
    ]
    payload = {"model": MODEL, "messages": messages, "temperature": 0.3}
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {API_KEY}"}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=90)
    if response.status_code != 200:
        raise RuntimeError(f"API 请求失败（{response.status_code}）：{response.text}")
    raw = response.json()["choices"][0]["message"]["content"]

    # ---- 解析 v2：按空行分块，每块内逐标签提取，缺啥跳啥 ----
    import re
    notes = {}
    for block in re.split(r"\n\s*\n", raw):
        m_word = re.search(r"词：(.+)", block)
        if not m_word:
            continue                          # 没有"词："标签的块直接跳过
        word = m_word.group(1).strip().lower()
        # 词形变化
        m_forms = re.search(r"词形：(.+)", block)
        forms = m_forms.group(1).strip() if m_forms else ""
        # 义项：抓义项1~3，"无"不算
        senses = []
        for i in (1, 2, 3):
            m = re.search(rf"义项{i}：(.+)", block)
            if m and m.group(1).strip() not in ("", "无"):
                senses.append(m.group(1).strip())
        # 例句：例1~3 和 译1~3 配对
        examples = []
        for i in (1, 2, 3):
            m_en = re.search(rf"例{i}：(.+)", block)
            m_zh = re.search(rf"译{i}：(.+)", block)
            if m_en:
                examples.append((m_en.group(1).strip(),
                                 m_zh.group(1).strip() if m_zh else ""))
        notes[word] = {"forms": forms, "senses": senses, "examples": examples}
    return notes
# ---- 降难重写：把质检报告里的具体生词，点名要求 AI 替换 ----
SIMPLIFY_PROMPT = """你是一位英语分级读物改写专家。用户会给你一篇短文和一份"过于罕见
的单词清单"。请重写这篇短文，要求：

1. 清单中的每个词，都必须替换成更常见的同义表达（或改写句子绕开它）
2. 清单之外的正文内容、故事情节、长度，尽量保持原样
3. 改写后仍然遵守原来的输出格式合约：标题：/风格：/难度：/导读：/正文：/表达：

不许输出任何解释，直接输出改写后的完整结果。"""

def simplify_passage(passage, hard_words):
    """对不合格的片段做定点降难。passage = 生成函数返回的字典
    hard_words = [(word, zipf), ...] 扫描器揪出的生词清单
    返回：改写后的同结构字典；失败则抛异常"""
    word_list = "、".join(w for w, s in hard_words)
    messages = [
        {"role": "system", "content": SIMPLIFY_PROMPT},
        {"role": "user", "content":
            f"过于罕见的单词清单：{word_list}\n\n原文：\n"
            f"标题：{passage['title']}\n风格：{passage.get('style', '原创')}\n"
            f"难度：{passage['level']}\n导读：{passage['intro']}\n"
            f"正文：\n{passage['text']}\n表达：\n" + "\n".join(passage['expressions'])
        },
    ]
    payload = {"model": MODEL, "messages": messages, "temperature": 0.5}
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {API_KEY}"}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=90)
    if response.status_code != 200:
        raise RuntimeError(f"API 请求失败（{response.status_code}）：{response.text}")
    raw = response.json()["choices"][0]["message"]["content"]

    # 解析改写稿（同一套格式合约，老手艺）
    import re
    title = re.search(r"标题：(.+)", raw).group(1).strip()
    level = re.search(r"难度：(\S+)", raw).group(1).strip()
    intro = re.search(r"导读：(.+)", raw).group(1).strip()
    text  = re.search(r"正文：\n?(.+?)(?=\n表达：|\s*表达：)", raw, re.DOTALL).group(1).strip()
    expr_block = re.search(r"表达：\n?(.+)", raw, re.DOTALL).group(1).strip()
    exprs = [line.strip("- ").strip() for line in expr_block.split("\n") if line.strip()]
    return {"title": title, "level": level, "intro": intro,
            "text": text, "expressions": exprs}