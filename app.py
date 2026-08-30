# ============================================================
# 地道英语思维训练器 —— 第五步下半场：登录注册 + 数据隔离
# 运行方法：在终端输入  streamlit run app.py
# ============================================================

# ---------- 1. 导入库 ----------
import streamlit as st
import glm_api
import database


# ---------- 2. 初始化数据库 ----------
database.init_db()


# ---------- 3. 页面基础设置 ----------
st.set_page_config(
    page_title="地道英语思维训练器",
    page_icon="🇬🇧",
    layout="wide",
)


# ============================================================
# 4. ★ 登录闸门：没登录的人只能看到下面的登录界面
# ============================================================
if "user_id" not in st.session_state:
    st.title("🔐 地道英语思维训练器")
    st.caption("登录后开始你的地道英语思维训练")

    # st.tabs：像浏览器标签页一样的两个可切换面板
    tab_login, tab_register = st.tabs(["🔑 登录", "📝 注册"])

    # ---- 登录面板 ----
    with tab_login:
        login_username = st.text_input("用户名", key="login_username")
        # type="password"：输入时显示圆点●●●，防止被人偷看
        login_password = st.text_input("密码", type="password", key="login_password")
        if st.button("登录", type="primary", use_container_width=True):
            user_id = database.verify_user(login_username, login_password)
            if user_id is not None:
                # 登录成功：把身份写进"小抄"，再刷新页面
                st.session_state["user_id"] = user_id
                st.session_state["username"] = login_username.strip()
                st.rerun()
            else:
                # 安全习惯：统一提示，不暴露"到底是用户名错还是密码错"
                st.error("用户名或密码错误")

    # ---- 注册面板 ----
    with tab_register:
        reg_username = st.text_input("用户名（不能有空格）", key="reg_username")
        reg_password = st.text_input("密码（至少 6 位）", type="password", key="reg_password")
        reg_password2 = st.text_input("再输一遍密码确认", type="password", key="reg_password2")
        if st.button("注册", use_container_width=True):
            if reg_password != reg_password2:
                st.error("两次输入的密码不一致")
            else:
                ok, msg = database.register_user(reg_username, reg_password)
                if ok:
                    # 注册成功 → 直接自动登录，省得再点一次
                    st.session_state["user_id"] = database.verify_user(reg_username, reg_password)
                    st.session_state["username"] = reg_username.strip()
                    st.rerun()
                else:
                    st.error(msg)

    # ★ 关键一行：没登录就到此为止！后面的主界面一行都不会执行
    st.stop()


# ============================================================
# 能走到这里 = 已登录，下面全部是主界面
# ============================================================

# ---------- 5. 欢迎语 + 输入框 ----------
st.title("🇬🇧 地道英语思维训练器")
st.caption(f"你好，{st.session_state['username']}！输入中文或中式英语 → AI 母语导师帮你纠正")

user_input = st.text_area(
    "✍️ 请输入你的中文或中式英语：",
    placeholder="例如：I very like play basketball.（或直接写中文：我非常喜欢打篮球）",
    height=120,
)


# ---------- 6. 分析按钮 ----------
analyze_clicked = st.button("🔍 开始分析", type="primary", use_container_width=True)


# ---------- 7. 核心逻辑：分析 + 按人存档 ----------
st.subheader("📋 分析结果")

if analyze_clicked:
    if user_input.strip() == "":
        st.warning("⚠️ 请先输入内容，再点击「开始分析」哦～")
    else:
        with st.spinner("🤖 AI 导师正在分析中，请稍候几秒……"):
            try:
                analysis = glm_api.analyze_english(user_input)
                # ★ 存档时带上"当前登录人"的编号，数据各归其主
                database.save_record(st.session_state["user_id"], user_input, analysis)
                st.session_state["last_input"] = user_input
                st.session_state["last_analysis"] = analysis
                st.session_state.pop("review_record", None)
                st.toast("✅ 分析完成，已存入你的历史记录！")
            except Exception as e:
                st.error(f"❌ 调用 AI 失败：{e}")


# ---------- 8. 结果展示 ----------
if "last_analysis" in st.session_state:
    st.markdown(f"**📝 你的输入：** {st.session_state['last_input']}")
    st.markdown(st.session_state["last_analysis"])
    st.divider()
else:
    st.info("👆 在上方输入内容并点击「开始分析」，结果会显示在这里。")


# ---------- 9. 随机复习区 ----------
st.subheader("🎲 随机复习")
st.caption("随机抽一条【你自己的】历史记录 → 先看原句自己纠正 → 再展开对答案")

if st.button("🎲 抽一条来复习", use_container_width=True):
    record = database.get_random_record(st.session_state["user_id"])
    if record is None:
        st.warning("你的历史上还没有记录，先去完成一次练习吧～")
    else:
        st.session_state["review_record"] = record

if "review_record" in st.session_state:
    r_id, r_input, r_analysis, r_time = st.session_state["review_record"]
    with st.container(border=True):
        st.markdown(f"**📝 历史原句（#{r_id} · {r_time}）：**")
        st.markdown(f"> {r_input}")
        with st.expander("🙈 先自己纠正，再点开对答案", expanded=False):
            st.markdown(r_analysis)
else:
    st.caption("（点击上方按钮开始复习）")


# ---------- 10. 侧边栏：用户 + 历史记录 + 导出 ----------
with st.sidebar:
    st.title("📚 历史记录")
    st.caption(f"👤 当前用户：{st.session_state['username']}")

    current_user_id = st.session_state["user_id"]
    count = database.get_record_count(current_user_id)
    st.caption(f"已保存练习：{count} 条")

    records = database.get_all_records(current_user_id)

    if len(records) == 0:
        st.info("还没有记录，快去完成第一次练习吧！")
    else:
        for record in records:
            record_id, input_text, analysis_text, created_at = record
            short_title = input_text.replace("\n", " ")
            if len(short_title) > 20:
                short_title = short_title[:20] + "…"
            with st.expander(f"#{record_id} {short_title}"):
                st.caption(f"🕒 {created_at}")
                st.markdown(analysis_text)

    st.divider()

    if count > 0:
        st.download_button(
            label="⬇️ 导出全部记录（Markdown）",
            data=database.export_records(current_user_id),
            file_name=f"{st.session_state['username']}的英语练习记录.md",
            mime="text/markdown",
            use_container_width=True,
        )

    confirm = st.checkbox("确认要清空全部历史吗？")
    if st.button("🗑️ 清空历史", disabled=not confirm):
        database.clear_all_records(current_user_id)
        st.rerun()

    st.divider()

    # ---------- 11. ★ 退出登录 ----------
    if st.button("🚪 退出登录", use_container_width=True):
        # 连页面上的"小抄"一起清掉，防止下一个人看到上个用户的内容
        for key in ["user_id", "username", "last_input", "last_analysis", "review_record"]:
            st.session_state.pop(key, None)
        st.rerun()


# ---------- 12. 页脚 ----------
st.divider()
st.caption("🇬🇧 地道英语思维训练器 · 数据只保存在本地 history.db，不上传任何服务器")