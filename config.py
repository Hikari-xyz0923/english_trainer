# ============================================================
# config.py —— 配置文件：从环境变量 / .env 读取 API Key
#
# 为什么改成这样：
#   以前 Key 是明文写在这行代码里的，一旦这个文件夹发给别人、
#   传到 GitHub、或者被人截屏，Key 就等于公开了，别人可以拿它
#   刷你的额度。现在 Key 存在项目目录下的 .env 文件里，
#   而 .env 已经写进 .gitignore，不会被提交。
#
# 怎么用：
#   在项目目录建一个 .env 文件（和本文件同一层），内容一行：
#       ZHIPU_API_KEY=你的key
#   或者设置环境变量 ZHIPU_API_KEY，优先级比 .env 高。
# ============================================================

import os


def _read_env_file(path):
    """读一个极简的 .env 文件：每行 KEY=VALUE，忽略空行和 # 注释。"""
    values = {}
    if not os.path.exists(path):
        return values
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                values[key.strip()] = val.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_FILE_VALUES = _read_env_file(os.path.join(_BASE_DIR, ".env"))

# 优先环境变量，其次 .env 文件
API_KEY = os.environ.get("ZHIPU_API_KEY") or _ENV_FILE_VALUES.get("ZHIPU_API_KEY", "")

# 智谱 GLM 的接口地址（固定不变，不用动）
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# 使用的模型：glm-4-flash 免费、速度快，学习用完全够
# 如果以后报"模型不存在"，去智谱控制台看可用模型列表，换个名字即可
MODEL = os.environ.get("ZHIPU_MODEL") or _ENV_FILE_VALUES.get("ZHIPU_MODEL", "glm-4-flash")

if not API_KEY:
    raise RuntimeError(
        "没有读到 API Key。\n"
        "请在项目目录（和 config.py 同一层）新建一个 .env 文件，写入一行：\n"
        "    ZHIPU_API_KEY=你的key\n"
        "（Key 从 https://open.bigmodel.cn 控制台获取；也可以改用环境变量 ZHIPU_API_KEY）"
    )
