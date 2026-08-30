# ============================================================
# cleanup_test_data.py —— 一次性清理脚本：只删【测试】记录
# 用完后这个文件可以删掉，不影响主程序
# ============================================================

import database   # 复用我们自己写的数据库模块，不重复造轮子

database.init_db()   # 确保数据库和表存在（已存在则什么都不做）

conn = database.get_connection()
cursor = conn.cursor()

# LIKE = 模糊匹配；% 是通配符，代表"任意内容"
# 整句意思：删除 input_text 里包含"【测试】"四个字的所有行
# （照旧用 ? 占位符传参，安全带系好）
cursor.execute(
    "DELETE FROM records WHERE input_text LIKE ?",
    ("%【测试】%",),
)

print(f"✅ 已删除 {cursor.rowcount} 条测试记录")   # rowcount：刚才删了几行
conn.commit()
conn.close()

print(f"📚 剩余真实记录：{database.get_record_count()} 条")