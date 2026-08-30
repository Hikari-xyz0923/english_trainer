# ============================================================
# database.py —— 数据库模块（第五步下半场版：用户 + 数据隔离）
# 两张表：
#   users   —— 用户名册（账号 + 密码指纹）
#   records —— 练习记录（★ 每条都归属某个用户）
# ============================================================

import sqlite3
import hashlib
import bcrypt                 # 负责把密码变成"指纹"
from datetime import datetime

DB_NAME = "history.db"


def get_connection():
    """获取数据库连接 ≈ 翻开笔记本"""
    return sqlite3.connect(DB_NAME)


def init_db():
    """初始化数据库：表不存在就创建（已存在则跳过）。
    ⚠️ 本次给 records 表新增了 user_id 列，必须删除旧 history.db
    让它按新结构重建（原因见教程正文）。
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ---- 表1：用户名册 ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,   -- UNIQUE：全表禁止重名
            password_hash TEXT NOT NULL,          -- 只存密码"指纹"，绝不存明文
            created_at    TEXT NOT NULL
        )
    """)

    # ---- 表2：练习记录（★ 新增 user_id：这条记录属于谁）----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,       -- ★ 归属人的编号
            input_text    TEXT NOT NULL,
            analysis_text TEXT NOT NULL,
            created_at    TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ---------- 练习记录模块（★ 每个函数都必须带上 user_id）----------

def save_record(user_id, input_text, analysis_text):
    """保存一条练习记录（必须写明归属人）"""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute(
        "INSERT INTO records (user_id, input_text, analysis_text, created_at) "
        "VALUES (?, ?, ?, ?)",
        (user_id, input_text, analysis_text, now),
    )
    conn.commit()
    conn.close()




def get_all_records(user_id):
    """取出【这个人】的全部记录，最新的在最上面"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, input_text, analysis_text, created_at "
        "FROM records WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    )
    records = cursor.fetchall()
    conn.close()
    return records


def get_record_count(user_id):
    """统计【这个人】有多少条记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM records WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_random_record(user_id):
    """从【这个人】的记录里随机抽一条（复习用）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, input_text, analysis_text, created_at "
        "FROM records WHERE user_id = ? ORDER BY RANDOM() LIMIT 1",
        (user_id,),
    )
    record = cursor.fetchone()
    conn.close()
    return record


def export_records(user_id):
    """把【这个人】的全部记录拼成 Markdown 文本（导出用）"""
    records = get_all_records(user_id)
    lines = ["# 我的英语练习记录\n"]
    for r_id, r_input, r_analysis, r_time in records:
        lines.append(f"## 练习 #{r_id}（{r_time}）\n")
        lines.append(f"**输入：** {r_input}\n")
        lines.append(r_analysis + "\n")
        lines.append("\n---\n")
    return "\n".join(lines)


def clear_all_records(user_id):
    """清空【这个人】的记录（别人的不受影响）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ---------- 用户管理模块 ----------

def hash_password(password):
    """用 bcrypt 生成密码"指纹"。

    相比旧的 sha256，两大升级：
    ① 自带随机盐：同一个密码，每次算出的指纹都不一样！
       盐就藏在指纹字符串里，所以登录时能验证；
       黑客预计算的"密码→指纹"对照表彻底作废。
    ② 故意慢：算一次约 0.1 秒。你登录一次毫无感觉，
       黑客想试一亿次密码，就要付一亿次的时间代价。
    """
    salt = bcrypt.gensalt()   # 掷骰子：生成一串随机"盐"
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")   # 转回字符串才能存进数据库


def register_user(username, password):
    """注册新用户，返回 (是否成功, 提示信息)"""
    username = username.strip()

    # 三道安检
    if not username or not password:
        return False, "用户名和密码都不能为空"
    if " " in username:
        return False, "用户名里不能有空格"
    if len(password) < 6:
        return False, "密码至少要 6 位哦"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone() is not None:
        conn.close()
        return False, "这个用户名已经被注册啦，换一个试试～"

    cursor.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    conn.close()
    return True, "注册成功！🎉"


def update_password_hash(user_id, password):
    """把某用户的指纹升级为 bcrypt 版（给老用户"透明迁移"用）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(password), user_id),
    )
    conn.commit()
    conn.close()


def verify_user(username, password):
    """登录验证：成功返回用户编号，失败返回 None。

    ★ 兼容两种指纹格式：
      新指纹：以 $2 开头（bcrypt 的签名）
      旧指纹：64 位十六进制文本（旧 sha256）
    老用户登录成功的那一刻，顺手把指纹升级成 bcrypt——
    用户毫无察觉，安全悄悄升级。这招叫"透明迁移"，
    是真实公司升级加密算法的标准做法。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        (username.strip(),),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None   # 查无此人

    user_id, password_hash = row

    if password_hash.startswith("$2"):
        # ---- 新指纹：直接用 bcrypt 验证 ----
        # checkpw 会自动从指纹里取出盐，用同样的盐"磨"你输入的密码再比对
        if bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
            return user_id
        return None
    else:
        # ---- 旧指纹：先用老 sha256 方法验证 ----
        if hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash:
            # 密码正确 → 趁机升级成 bcrypt 指纹
            update_password_hash(user_id, password)
            return user_id
        return None


# ---------- 独立测试区（只读，★ 挑战7升级版）----------
if __name__ == "__main__":
    print("🧪 只读测试中……")
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, created_at FROM users")
    rows = cursor.fetchall()
    conn.close()

    print(f"👥 当前共 {len(rows)} 个用户：")
    for row in rows:
        user_id, username, password_hash, created_at = row
        if password_hash.startswith("$2"):
            kind = "新·bcrypt"
        else:
            kind = "旧·sha256（下次登录自动升级）"
        print(f"  #{user_id} {username} [{kind}]")
        print(f"      指纹：{password_hash}")