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
        