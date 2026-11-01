# ============================================================
# database.py —— 数据库模块（第五步下半场版：用户 + 数据隔离）
# 两张表：
#   users   —— 用户名册（账号 + 密码指纹）
#   records —— 练习记录（★ 每条都归属某个用户）
# ============================================================

import sqlite3
import hashlib
import bcrypt                 # 负责把密码变成“指纹"
from datetime import datetime
from pathlib import Path

import srs                    # 间隔重复算法（纯函数，本模块只调不改）

# 使用模块所在目录的绝对路径，避免从其他目录启动 Streamlit 时 SQLite 无法打开。
DB_NAME = str(Path(__file__).resolve().with_name("history.db"))


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
    # ---- 表3：用户设置（★ 新增：记住每个用户的词汇量）----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id    INTEGER PRIMARY KEY,   -- 主键：一个用户只有一行设置
            vocab_size TEXT NOT NULL            -- 词汇量（文本存储，兼容数字和区间）
        )
    """)
        # ---- 表4：AI 生成的片段仓库（★ 新增）----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,      -- 标题（AI 起的名）
            level       TEXT NOT NULL,      -- 难度标签（🌱/🌿/🌳）
            domain      TEXT NOT NULL,      -- 领域（如"深海科考"）
            intro       TEXT NOT NULL,      -- 中文导读
            text        TEXT NOT NULL,      -- 英文正文
            expressions TEXT NOT NULL,      -- 地道表达（一行一个）
            words       INTEGER NOT NULL,   -- 词数（展示用）
            created_by  INTEGER NOT NULL,   -- 谁生成的（只能看自己仓库?不!共享,见下）
            created_at  TEXT NOT NULL
        )
    """)
    # ---- 表5：生词本（★ 每个用户收编的表达，私人财产）----
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS collected_words (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,       -- 属于哪个用户
                expression  TEXT NOT NULL,          -- 表达本身
                meaning     TEXT DEFAULT '',        -- 中文释义
                source      TEXT DEFAULT '',        -- 出处（哪篇片段）
                usage       TEXT DEFAULT '',        -- ★ 用法例句（AI 补课用，一步到位）
                met_count   INTEGER DEFAULT 1,      -- 重遇计数（为12次重遇引擎预留）
                created_at  TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        # ---- 表6：打卡记录（user_id+日期 唯一，天然防重复打卡）----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checkin_records (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            checkin_date TEXT NOT NULL
        )
    """)
    # ---- 表7：积分流水账（每笔积分变动都留痕）----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS point_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            amount     INTEGER NOT NULL,   -- 正数=得，负数=扣
            reason     TEXT NOT NULL,      -- 事由
            created_at TEXT NOT NULL
        )
    """)
    # ---- 表8：错误标签（错误画像的缓存，避免每次打开都重新调 AI）----
    # record_id 做主键：一条记录只归一次类，重复写会覆盖（重扫时用得上）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS error_tags (
            record_id  INTEGER PRIMARY KEY,
            user_id    INTEGER NOT NULL,   -- 冗余存一份，查某人的标签不用 join
            tags       TEXT NOT NULL,      -- 逗号分隔的错误类型，如 "介词,冠词"
            note       TEXT DEFAULT '',    -- 一句话说明（AI 给的错误点摘要）
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    

def update_word_notes(word_id, user_id, meaning, usage):
    """把 AI 补课的释义和用法写进生词卡。
    UPDATE = 修改已有记录；WHERE 同时校验 id 和 user_id（只能改自己的词）。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE collected_words SET meaning = ?, usage = ? WHERE id = ? AND user_id = ?",
        (meaning, usage, word_id, user_id)
    )
    conn.commit()
    conn.close()
# ---------- AI 片段仓库模块（★ 新增）----------

def save_passage(title, level, domain, intro, text, expressions, created_by):
    """存入一篇 AI 生成的片段（expressions 传列表，存成一行一个）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO passages (title, level, domain, intro, text, expressions, "
        "words, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, level, domain, intro, text,
         "\n".join(expressions),                       # 列表 → 换行分隔的文本
         len(text.split()),                            # 词数现场统计
         created_by,
         datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    conn.close()


def get_all_passages():
    """取出全部 AI 片段（全员共享），最新的在前"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, level, domain, intro, text, expressions, words, created_at "
        "FROM passages ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_passage(passage_id):
    """按编号删除一个 AI 片段。
    passage_id 是 passages 表里的主键（馆藏编号）。
    返回实际删中的行数：1 = 删成功；0 = 没匹配到任何行。"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM passages WHERE id = ?", (passage_id,))
    deleted_count = c.rowcount   # 先出生：接住本条 SQL 实际影响的行数
    conn.commit()
    conn.close()
    return deleted_count         # 后使用：把战果交还给调用方
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
    """清空【这个人】的记录（别人的不受影响）
    错误标签是记录的附属品——记录没了，标签也得跟着走，
    否则重扫时会拿旧标签配新记录（id 会被 AUTOINCREMENT 复用吗？不会，
    但留着孤儿行会让统计里凭空多出几类错误）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM error_tags WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ---------- 错误画像：标签的存与取 ----------

def get_untagged_records(user_id, limit=15):
    """取出还没归过类的记录（老的先归，保证顺序稳定）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT r.id, r.input_text, r.analysis_text, r.created_at "
        "FROM records r LEFT JOIN error_tags t ON r.id = t.record_id "
        "WHERE r.user_id = ? AND t.record_id IS NULL "
        "ORDER BY r.id ASC LIMIT ?",
        (user_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def count_untagged(user_id):
    """还有多少条没归类（界面上显示"待扫描 N 条"）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM records r LEFT JOIN error_tags t ON r.id = t.record_id "
        "WHERE r.user_id = ? AND t.record_id IS NULL",
        (user_id,),
    )
    n = cursor.fetchone()[0]
    conn.close()
    return n


def save_error_tags(user_id, items):
    """批量写入归类结果。items = [(record_id, "介词,冠词", "说明"), ...]
    用 INSERT OR REPLACE：同一条重复归类时以最后一次为准。"""
    if not items:
        return 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT OR REPLACE INTO error_tags (record_id, user_id, tags, note, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [(rid, user_id, tags, note, now) for rid, tags, note in items],
    )
    conn.commit()
    conn.close()
    return len(items)


def get_error_tags(user_id):
    """取出这个人全部归类结果：[(record_id, tags, note), ...]"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT record_id, tags, note FROM error_tags WHERE user_id = ?",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


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

# ---------- 词汇量记忆模块（★ 新增）----------

def save_vocab_size(user_id, vocab_size):
    """保存/更新用户的词汇量（永久记住，存硬盘）。
    INSERT OR REPLACE = "有则覆盖，无则插入"（upsert）：
    同一个用户反复保存时永远只有一行最新数据，不会越存越多。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_settings (user_id, vocab_size) VALUES (?, ?)",
        (user_id, str(vocab_size)),
    )
    conn.commit()
    conn.close()


def get_vocab_size(user_id):
    """读取记住的词汇量；从没存过返回 None"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vocab_size FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def clear_vocab_size(user_id):
    """忘掉已存的词汇量（用户想重新测评时用）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
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
# ==================== 生词本四件套 ====================

def add_collected_word(user_id, expression, meaning="", source=""):
    """收编一个表达进生词本。已存在则拒绝重复收编，返回 False。"""
    conn = get_connection()
    c = conn.cursor()
    # 先查：这个用户的本子里有没有同款？
    c.execute("SELECT id FROM collected_words WHERE user_id = ? AND expression = ?",
              (user_id, expression))
    if c.fetchone():                      # 查到了 = 已存在
        conn.close()
        return False
    # 没查到 = 新词，正式入库（usage 列用默认值 ''，等 AI 补课再填）
    c.execute(
        "INSERT INTO collected_words (user_id, expression, meaning, source) VALUES (?, ?, ?, ?)",
        (user_id, expression, meaning, source)
    )
    conn.commit()
    conn.close()
    return True


def get_collected_words(user_id):
    """取出某用户的全部生词，最新的在前。
    注意：SELECT 列顺序 = 界面解包顺序，一动两个都要动！"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, expression, meaning, source, met_count, created_at "
        "FROM collected_words WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def delete_collected_word(word_id, user_id):
    """从生词本移除一个词。WHERE 双重校验：只能删自己本子里的词。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM collected_words WHERE id = ? AND user_id = ?",
              (word_id, user_id))
    conn.commit()
    conn.close()


def update_word_notes(word_id, user_id, meaning, usage):
    """把 AI 补课的释义和用法写进生词卡（UPDATE = 修改已有记录）。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE collected_words SET meaning = ?, usage = ? WHERE id = ? AND user_id = ?",
        (meaning, usage, word_id, user_id)
    )
    conn.commit()
    conn.close()



def get_checkin_streak(user_id):
    """计算连续打卡天数（连击数）。
    逻辑：从今天（或昨天）开始往回数，日期必须一天不落地连续。
    今天还没打卡也不慌——只要昨天在连，连击仍然存活（今天打了就续上）。"""
    conn = get_connection()
    c = conn.cursor()
    # 取该用户所有打卡日期，倒序（新→旧）
    c.execute(
        "SELECT checkin_date FROM checkin_records WHERE user_id = ? ORDER BY checkin_date DESC",
        (user_id,)
    )
    dates = [row[0] for row in c.fetchall()]
    conn.close()
    if not dates:
        return 0
    # 去重：万一同一天写进两条（手动补数据、并发打卡都会造成），
    # 逐天核对会在"同一天出现两次"那里卡住，连击直接算成 1 天。
    dates = sorted(set(dates), reverse=True)
    # 用 Python 的日期运算做"连续性检查"
    import datetime
    today = datetime.date.today()
    # 起点容错：如果今天没打，看昨天（连击还活着，等今天续）
    start = today if dates[0] == today.isoformat() else today - datetime.timedelta(days=1)
    if dates[0] != start.isoformat():
        return 0                      # 昨天也没打 → 连击已断
    streak = 0
    expected = start
    for d in dates:                   # 逐天核对：日期必须一天天递减
        if d == expected.isoformat():
            streak += 1
            expected -= datetime.timedelta(days=1)
        else:
            break                     # 断了一天，后面全不算
    return streak
# ==================== 打卡与积分系统 ====================

def ensure_points_column():
    """透明迁移：给 users 表补 total_points 列（老用户自动补齐，新表直接建就有）。"""
    try:
        conn = get_connection()
        conn.execute("ALTER TABLE users ADD COLUMN total_points INTEGER DEFAULT 0")
        conn.commit()
        conn.close()
    except Exception:
        pass   # 列已存在 = 老 situations，静默跳过


def add_points(user_id, amount, reason):
    """积分记账：加（正数）或扣（负数），并写入流水账。
    amount = 变动数值；reason = 事由（如 '每日打卡'）"""
    conn = get_connection()
    c = conn.cursor()
    # ① 给总分加减（SQL 直接算，不读出来再写回——原子操作，不怕并发）
    c.execute("UPDATE users SET total_points = total_points + ? WHERE id = ?",
              (amount, user_id))
    # ② 流水账：每一笔都留痕
    c.execute(
        "INSERT INTO point_logs (user_id, amount, reason, created_at) "
        "VALUES (?, ?, ?, datetime('now', 'localtime'))",
        (user_id, amount, reason)
    )
    conn.commit()
    conn.close()


def get_total_points(user_id):
    """查某用户的当前总积分"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT total_points FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def has_checked_in_today(user_id):
    """判断今天是否已打卡（防止重复打卡刷分）"""
    conn = get_connection()
    c = conn.cursor()
    # date('now','localtime') = 今天的日期字符串，如 '2025-01-15'
    c.execute(
        "SELECT id FROM checkin_records WHERE user_id = ? AND checkin_date = date('now','localtime')",
        (user_id,)
    )
    found = c.fetchone()
    conn.close()
    return found is not None


def do_checkin(user_id, points):
    """执行打卡：写打卡记录 + 加积分。返回 False = 今天已打过。"""
    if has_checked_in_today(user_id):
        return False
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO checkin_records (user_id, checkin_date) "
        "VALUES (?, date('now','localtime'))",
        (user_id,)
    )
    conn.commit()
    conn.close()
    add_points(user_id, points, "每日打卡")
    return True
def get_today_stats(user_id):
    """查用户今天的任务相关行为统计。返回字典：
    analyzed 今天句子分析次数 / collected 今天收编生词数"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) FROM records WHERE user_id = ? AND date(created_at) = date('now','localtime')",
        (user_id,)
    )
    analyzed = c.fetchone()[0]           # COUNT(*) 永远返回一行一列
    c.execute(
        "SELECT COUNT(*) FROM collected_words WHERE user_id = ? AND date(created_at) = date('now','localtime')",
        (user_id,)
    )
    collected = c.fetchone()[0]
    conn.close()
    return {"analyzed": analyzed, "collected": collected}


def award_once_today(user_id, amount, reason):
    """当日首次奖励：同一 reason 今天第一次才发分，之后静默跳过（防刷分）。
    返回 True = 本次发了分；False = 今天已领过。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM point_logs WHERE user_id = ? AND reason = ? "
        "AND date(created_at) = date('now','localtime')",
        (user_id, reason)
    )
    already = c.fetchone()
    conn.close()
    if already:
        return False
    add_points(user_id, amount, reason)   # 复用记账函数，流水自动留痕
    return True


def task_done_today(user_id, reason):
    """查某任务今天是否已完成（用于任务清单的 ✅/⬜ 显示）"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM point_logs WHERE user_id = ? AND reason = ? "
        "AND date(created_at) = date('now','localtime')",
        (user_id, reason)
    )
    found = c.fetchone()
    conn.close()
    return found is not None


# ==================== 成长页 / 任务页：读明细 ====================
# 上面那些函数只回答"一共多少分"，成长页要的是"这些分都是怎么来的"。

def get_point_logs(user_id, limit=20):
    """积分流水，新的在前。返回 [(金额, 事由, 时间), ...]

    为什么不一并返回总分：总分查 users.total_points 一句就够，
    这里只负责"明细"，两件事分开查，缓存逻辑才不会互相拖累。
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT amount, reason, created_at FROM point_logs "
        "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, int(limit))
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_checkin_dates(user_id, days=42):
    """最近 days 天里打过卡的日期集合（'YYYY-MM-DD'）。

    返回集合而不是列表：日历要对每一天问"这天打了吗"，
    集合是 O(1) 判断，列表每次都得扫一遍。
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT checkin_date FROM checkin_records "
        "WHERE user_id = ? AND checkin_date >= date('now','localtime', ?)",
        (user_id, f"-{int(days)} day")
    )
    dates = {row[0] for row in c.fetchall()}
    conn.close()
    return dates


def get_points_by_day(user_id, days=7):
    """最近 days 天每天的得分合计。返回 {'2026-11-01': 25, ...}

    没有得分的那天不会出现在字典里——调用方按 .get(day, 0) 取，
    专门用来区分"这天 0 分"和"这天压根没数据"。
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT date(created_at) AS d, SUM(amount) FROM point_logs "
        "WHERE user_id = ? AND date(created_at) >= date('now','localtime', ?) "
        "GROUP BY d",
        (user_id, f"-{int(days) - 1} day")
    )
    rows = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows if r[0]}


def get_total_checkins(user_id):
    """累计打卡天数（历史总和，和"连击"不是一回事：断签也保留）"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM checkin_records WHERE user_id = ?", (user_id,))
    n = c.fetchone()[0]
    conn.close()
    return n


# ==================== 间隔重复（生词复习排期）====================
# 算法在 srs.py，这里只负责存取。分开的理由：算法要能被单独跑测试，
# 而且以后想换成 FSRS 之类，只要改 srs.py，不用动 SQL。

def ensure_srs_columns():
    """透明迁移：给 collected_words 补上间隔重复需要的五列。

    为什么用 PRAGMA 先查列再 ALTER，而不是 try/except：
      SQLite 的 ALTER TABLE 失败会让整个事务进入异常状态，
      在一个循环里连续 try 五条，前一条失败后后面可能全失败。
      先查一次表结构，只补缺的那几列，最稳。
    """
    conn = get_connection()
    existing = {row[1] for row in conn.execute("PRAGMA table_info(collected_words)")}
    additions = [
        ("ease", "REAL DEFAULT 2.5"),        # 难度因子
        ("interval_days", "INTEGER DEFAULT 0"),   # 当前间隔（天）
        ("reps", "INTEGER DEFAULT 0"),       # 连续答对次数
        ("lapses", "INTEGER DEFAULT 0"),     # 累计忘了几次
        ("due_date", "TEXT"),                # 下次复习日（NULL = 新词，今天就能复习）
    ]
    for name, decl in additions:
        if name not in existing:
            conn.execute(f"ALTER TABLE collected_words ADD COLUMN {name} {decl}")
    conn.commit()
    conn.close()


def get_due_words(user_id, limit=20):
    """今天该复习的词。返回 [(id, 表达, 释义, 用法, 出处, ease, interval, reps, lapses, due), ...]

    排序规则：**到期的旧词在前，没复习过的新词在后**。
      反过来（新词优先）的话，攒了 50 个新词，那些"明天就要忘"的旧词
      永远排不到，间隔重复就白做了。
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, expression, meaning, usage, source, "
        "       ease, interval_days, reps, lapses, due_date "
        "FROM collected_words "
        "WHERE user_id = ? AND (due_date IS NULL OR due_date <= date('now','localtime')) "
        "ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, "
        "         due_date ASC, id ASC "
        "LIMIT ?",
        (user_id, int(limit))
    )
    rows = c.fetchall()
    conn.close()
    return rows


def count_due_words(user_id):
    """今天到期（含新词）的词数——首页那个"N 个待复习"就是它。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) FROM collected_words "
        "WHERE user_id = ? AND (due_date IS NULL OR due_date <= date('now','localtime'))",
        (user_id,)
    )
    n = c.fetchone()[0]
    conn.close()
    return n


def apply_review(word_id, user_id, quality):
    """给一个词打一次分，按 SM-2 算出下次复习日期并写回。

    返回 (ease, interval, reps, lapses, due_date)；词不存在返回 None。

    为什么先读再算再写，而不是一条 SQL 搞定：
      SM-2 依赖当前 ease/interval/reps 三个值，纯 SQL 写不出来，
      而且算法要能单测。这里多一次 SELECT 换来可读性和可测性，值。
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT ease, interval_days, reps, lapses FROM collected_words "
        "WHERE id = ? AND user_id = ?",
        (word_id, user_id)
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return None

    new_ease, new_interval, new_reps, new_lapses, due = srs.review(
        row[0], row[1], row[2], row[3], quality
    )
    c.execute(
        "UPDATE collected_words SET ease = ?, interval_days = ?, reps = ?, "
        "       lapses = ?, due_date = ? WHERE id = ? AND user_id = ?",
        (new_ease, new_interval, new_reps, new_lapses, due.isoformat(), word_id, user_id)
    )
    conn.commit()
    conn.close()
    return new_ease, new_interval, new_reps, new_lapses, due


def get_srs_stats(user_id):
    """生词本的整体状态：总数 / 待复习 / 学习中的 / 已掌握的。

    口径说明：新词（reps=0）算"待复习"也算"学习中的"，
    因为它确实还没掌握；"已掌握"只看间隔是否撑过 21 天。
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT "
        "  COUNT(*), "
        "  SUM(CASE WHEN due_date IS NULL OR due_date <= date('now','localtime') "
        "           THEN 1 ELSE 0 END), "
        "  SUM(CASE WHEN reps > 0 AND COALESCE(interval_days,0) < 21 "
        "           THEN 1 ELSE 0 END), "
        "  SUM(CASE WHEN COALESCE(interval_days,0) >= 21 THEN 1 ELSE 0 END) "
        "FROM collected_words WHERE user_id = ?",
        (user_id,)
    )
    row = c.fetchone()
    conn.close()
    return {
        "total": row[0] or 0,
        "due": row[1] or 0,
        "learning": row[2] or 0,
        "mature": row[3] or 0,
    }
