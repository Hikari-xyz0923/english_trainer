# ============================================================
# 地道英语思维训练器 —— 最终版：双板块 + 双模式词汇测评
# 运行方法：在终端输入  streamlit run app.py
#
# 板块一「句子分析」：AI 纠错 + 随机复习（原有功能）
# 板块二「阅读营」  ：
#   📏 词汇量测评 —— ⚡快速粗测（20题）/ 🎓完整版VST（120题闯关）
#   📅 今日一篇   —— 每天自动轮换一篇名著片段
#   📚 片段图书馆 —— 按难度浏览全部公版名著片段
# ============================================================

# ---------- 1. 导入库 ----------
import streamlit as st
import glm_api
import database
import reading_content   # 阅读营素材库（粗测题库 + 名著片段）
import vst_data          # ★ VST 学术题库（10层×12题）
import rank_system
import ai_detector        # ★ 板块三：作文 AI 痕迹检测
import reading_tab    # 阅读营四个子页面（原第 7 节拆出）
from reading_tab import clear_vst_state   # 退出登录时清 VST 状态（与阅读营共用一份）

# ---------- 2. 初始化数据库 ----------
database.init_db()


# ---------- 3. 页面基础设置 ----------
st.set_page_config(
    page_title="地道英语思维训练器",
    page_icon="🇬🇧",
    layout="wide",
)


# ---------- 3.5 清理 VST 答题状态的小工具 ----------
# 已移到 reading_tab.py（阅读营和退出登录共用一份），从那里 import


# ============================================================
# 4. 登录闸门（原样保留）
# ============================================================
if "user_id" not in st.session_state:
    st.title("🔐 地道英语思维训练器")
    st.caption("登录后开始你的地道英语思维训练")
    tab_login, tab_register = st.tabs(["🔑 登录", "📝 注册"])

    with tab_login:
        login_username = st.text_input("用户名", key="login_username")
        login_password = st.text_input("密码", type="password", key="login_password")
        if st.button("登录", type="primary", use_container_width=True):
            user_id = database.verify_user(login_username, login_password)
            if user_id is not None:
                st.session_state["user_id"] = user_id
                st.session_state["username"] = login_username.strip()
                st.rerun()
            else:
                st.error("用户名或密码错误")

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
                    st.session_state["user_id"] = database.verify_user(reg_username, reg_password)
                    st.session_state["username"] = reg_username.strip()
                    st.rerun()
                else:
                    st.error(msg)

    st.stop()


# ============================================================
# 5. 已登录：标题 + 双板块
# ============================================================
st.title("🇬🇧 地道英语思维训练器")
st.caption(f"你好，{st.session_state['username']}！句子分析 × 每日阅读，双轨训练地道英语思维")

tab_analyze, tab_reading, tab_detect = st.tabs(["🔍 句子分析", "📖 阅读营", "🕵️ AI 痕迹检测"])


# ============================================================
# 6. 板块一：句子分析（原样保留）
# ============================================================
with tab_analyze:

    user_input = st.text_area(
        "✍️ 请输入你的中文或中式英语：",
        placeholder="例如：I very like play basketball.（或直接写中文：我非常喜欢打篮球）",
        height=120,
    )

    analyze_clicked = st.button("🔍 开始分析", type="primary", use_container_width=True)

    if analyze_clicked:
        if user_input.strip() == "":
            st.warning("⚠️ 请先输入内容，再点击「开始分析」哦～")
        else:
            with st.spinner("🤖 AI 导师正在分析中，请稍候几秒……"):
                try:
                    analysis = glm_api.analyze_english(user_input)
                    database.save_record(st.session_state["user_id"], user_input, analysis)
                    st.session_state["last_input"] = user_input
                    st.session_state["last_analysis"] = analysis
                    st.session_state.pop("review_record", None)
                    st.toast("✅ 分析完成，已存入你的历史记录！")
                    # 完成任务奖励：当日首次分析 +5 分（防刷：重复分析不加）
                    database.award_once_today(st.session_state["user_id"], 5, "完成句子分析")
                except Exception as e:
                    st.error(f"❌ 调用 AI 失败：{e}")

    if "last_analysis" in st.session_state:
        st.markdown(f"**📝 你的输入：** {st.session_state['last_input']}")
        st.markdown(st.session_state["last_analysis"])
        st.divider()
    else:
        st.info("👆 在上方输入内容并点击「开始分析」，结果会显示在这里。")

    # ---- 随机复习 ----
    st.subheader("🎲 随机复习")
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


# ============================================================
# 7. 板块二：阅读营
# ============================================================
with tab_reading:
    sub_vocab, sub_daily, sub_library, sub_words = st.tabs(
        ["📏 词汇测评", "🤖 每日荐读", "📚 片段图书馆", "📖 生词本"]
    )

    with sub_vocab:
        reading_tab.render_vocab()

    with sub_daily:
        reading_tab.render_daily()

    with sub_library:
        reading_tab.render_library()

    with sub_words:
        reading_tab.render_words()

# ============================================================
# 8. 侧边栏（新增：显示最新测评结果）
# ============================================================
with st.sidebar:
    st.title("📚 历史记录")
    st.caption(f"👤 当前用户：{st.session_state['username']}")

    # ★ 新增：把测评结果常驻显示在这里，每天打开都能看到自己的水平
    if "vst_result" in st.session_state:
        st.caption(f"📏 我的词汇量：约 {st.session_state['vst_result']:,} 词（🎓VST）")
    elif "vocab_result" in st.session_state:
        level_name, vocab_range, _ = st.session_state["vocab_result"]
        st.caption(f"📏 我的词汇水平：{level_name}（⚡粗测）")

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

    # ==================== 🏆 打卡面板 ====================
    # 透明迁移 + 取数据
    database.ensure_points_column()
    pts = database.get_total_points(st.session_state["user_id"])
    rank = rank_system.points_to_rank(pts)
    streak = database.get_checkin_streak(st.session_state["user_id"])

    st.markdown(f"### {rank['rank_name']}")
    st.markdown(f"**{rank['sub_name']}** · {rank['progress']}")
    st.caption(f"💎 积分 {pts} ｜ 🔥 连击 {streak} 天")

    # 距下次升级的提示
    if rank["next_need"] is not None:
        st.progress(min(pts / (pts + rank["next_need"]), 1.0),
                        text=f"再攒 {rank['next_need']} 分升级")
    else:
        st.success("👑 已达最高段位，传奇仍在继续")

    # 打卡按钮：今天没打才亮，打了就变灰（防手滑第二下）
    already = database.has_checked_in_today(st.session_state["user_id"])
    if st.button("📅 今日打卡" if not already else "✅ 今日已打卡",
                 disabled=already, use_container_width=True):
        # 连击奖励：基础 10 分 + 连击加成
        bonus = 15 if streak + 1 >= 30 else (5 if streak + 1 >= 3 else 0)
        database.do_checkin(st.session_state["user_id"], 10 + bonus)
        if bonus:
            st.toast(f"打卡成功！+{10 + bonus} 分（含连击奖励 +{bonus}）🎉")
        else:
            st.toast("打卡成功！+10 分 📅")
        st.rerun()

    # ==================== 🎯 今日任务 ====================
    stats = database.get_today_stats(st.session_state["user_id"])
    already = database.has_checked_in_today(st.session_state["user_id"])

    st.markdown("**🎯 今日任务**")
    # 任务清单：✅已完成 / ⬜未完成，右侧显示分值
    task_rows = [
        ("📅 每日打卡", already, 10),
        ("🧠 完成 1 次句子分析", database.task_done_today(st.session_state["user_id"], "完成句子分析"), 5),
        ("💎 收编 1 个生词", database.task_done_today(st.session_state["user_id"], "收编生词"), 2),
        ("📖 阅读 1 篇 AI 片段", database.task_done_today(st.session_state["user_id"], "阅读片段"), 8),
    ]
    done_count = 0
    for task_name, done, reward in task_rows:
        if done:
            done_count += 1
        st.markdown(f"{'✅' if done else '⬜'} {task_name}　`+{reward}分`")

    # 完成度进度条 + 一句激励
    st.progress(done_count / len(task_rows),
                text=f"今日完成 {done_count}/{len(task_rows)}")
    if done_count == len(task_rows):
        st.success("🎉 今日任务全部完成，书虫饱了！")
    elif done_count == 0:
        st.caption("新的一天，从一个打卡开始 ✨")
    st.divider()

    # 退出登录：连测评状态一起清干净，防止下一个人看到上一个人的答案
    if st.button("🚪 退出登录", use_container_width=True):
        for key in ["user_id", "username", "last_input", "last_analysis",
                    "review_record", "vocab_result", "vst_result"]:
            st.session_state.pop(key, None)
        clear_vst_state()
        st.rerun()


# ============================================================
# 8. 板块三：AI 痕迹检测
#    设计立场：不给"真假判决"，只给"痕迹清单"。
#    理由写在 ai_detector.py 顶部——没有任何方法能可靠判断一段文字
#    是不是 AI 写的，模型判自己都经常判错。所以这里做的是把可以当场
#    核对的数字摆出来，让人自己看哪些地方像、哪些地方不像。
# ============================================================
with tab_detect:

    st.subheader("🕵️ 作文 AI 痕迹检测")
    st.caption(
        "贴一段英文，逐条核对「像 AI 的地方」。这里不判真假——"
        "没有方法能可靠判断一段文字是不是 AI 写的，所以只给数字和原句，判断留给你。"
    )

    essay = st.text_area(
        "✍️ 粘贴英文（至少 40 词）",
        height=260,
        placeholder="粘贴你想核对的一段英文，比如作业、作文、或者一段 AI 生成的材料……",
        key="detect_input",
    )

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        do_detect = st.button("🔍 分析痕迹", type="primary", use_container_width=True)
    with col_d2:
        do_second = st.button("🤖 让模型给第二意见（约 20 秒）", use_container_width=True)

    if do_detect:
        if len(essay.split()) < 40:
            st.warning("⚠️ 至少 40 个英文单词再看。太短的文本，句长和用词分布都不可靠。")
        else:
            with st.spinner("正在统计句长、词频和模板短语……"):
                report = ai_detector.analyze(essay)
                report["_src"] = essay.strip()[:200]   # 记住这段是分析哪份文本，防止改了内容还显示旧报告
                st.session_state["detect_report"] = report

    rep = st.session_state.get("detect_report")

    # 文本被改过 → 旧报告作废，别让人看着旧数字以为新文本也是这个分
    if rep and rep.get("_src") and rep["_src"] != essay.strip()[:200]:
        st.info("文本已经改过了，点上面的「分析痕迹」重新算一次。")
        rep = None

    if rep:
        if not rep.get("ok"):
            st.warning(f"⚠️ {rep.get('message', '文本太短')}")
        else:
            s = rep["stats"]
            m1, m2, m3 = st.columns(3)
            m1.metric("痕迹分", f"{rep['score']} / 100")
            m2.metric("档位", rep["band"])
            m3.metric("规模", f"{s['words']} 词 · {s['sentences']} 句 · {s['paragraphs']} 段")

            st.progress(rep["score"] / 100, text="分越高，模板痕迹越重（不是概率）")

            if rep["main_reasons"]:
                st.markdown("**主要依据：**" + "、".join(rep["main_reasons"]))

            if rep["score"] >= 80:
                st.error("🔴 高度疑似 AI 生成：多句套话 + 句式过于齐整。")
            elif rep["score"] >= 60:
                st.warning("🟠 有明显 AI 痕迹：典型作文里不太会这么写。")
            elif rep["score"] >= 35:
                st.info("🟡 混合：有些地方像模板，有些地方像人。")
            else:
                st.success("🟢 更像人写的：没有明显模板腔，句子长短不齐。")

            # ---- 逐条信号表：每个数字都能当场核对 ----
            rows = [
                {
                    "信号": sig["name"],
                    "这段文字": sig["value"],
                    "人写常见": sig["human_hint"],
                    "AI 常见": sig["ai_hint"],
                    "判定": sig["verdict"],
                }
                for sig in rep["signals"]
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

            # ---- 证据句：命中的模板表达，连原句一起给 ----
            if rep["template_hits"]:
                with st.expander(f"📌 命中的模板化表达（{len(rep['template_hits'])} 处）", expanded=True):
                    for h in rep["template_hits"]:
                        st.markdown(f"**{h['phrase']}**")
                        st.markdown(f"> {h['sentence']}")

            with st.expander("📊 其他统计数字"):
                st.markdown(
                    f"- 平均句长：{s['avg_sent_len']} 词\n"
                    f"- 词汇多样性 MSTTR：{s['msttr']}%（每 50 词算一次不重复词占比，再平均）\n"
                    f"- 中频词（Zipf 3~4.5）占比：{s['mid_freq_ratio']}%\n"
                    f"- 每句逗号数：{s['comma_per_sentence']}"
                )

            # ---- 局限：必须写在界面上，不然会被当成检测器用 ----
            st.info(
                "**这套信号的适用边界。** 它抓的是「模板腔」和「句子太齐整」，"
                "不是「AI」本身，所以两类情况必然失效：\n\n"
                "① AI 刻意模仿文学风格（长句、少连接词、不用套话）——会被判低；\n"
                "② 人写的正式议论文（句式规整、没有口语）——可能被判高。\n\n"
                "它适合用来找「哪几句像模板」，不适合拿去指认谁用了 AI。"
            )

    # ---- 模型第二意见：默认不用，因为它慢，而且它判自己也不准 ----
    if do_second:
        if len(essay.split()) < 40:
            st.warning("⚠️ 至少 40 个英文单词。")
        else:
            with st.spinner("模型正在读这段文字……"):
                try:
                    # 把已有的统计结果一起交给模型，让它复核证据而不是凭语感拍结论
                    prev_rep = st.session_state.get("detect_report")
                    st.session_state["detect_second"] = ai_detector.second_opinion(essay, prev_rep)
                except Exception as e:
                    st.error(f"❌ 第二意见失败：{e}")

    if st.session_state.get("detect_second"):
        st.markdown("#### 🤖 模型的第二意见")
        second_text = st.session_state["detect_second"]
        st.markdown(second_text)

        # 模型结论和痕迹分打架时，明说。这种矛盾本身就是最有用的信息：
        # 说明"问模型"这条路不可靠，可核对的数字才靠得住
        prev = st.session_state.get("detect_report")
        if prev and prev.get("ok"):
            says_human = "更像人" in second_text
            says_ai = "更像 AI" in second_text
            score = prev["score"]
            if (says_human and score >= 60) or (says_ai and score < 35):
                st.warning(
                    "⚠️ 模型的判断和上面的痕迹分不一致。"
                    "这两种结果打架时，以能逐条核对的那个为准——模型的语感没有校准，"
                    "它会把自己写过的东西判成人写的。"
                )

        st.caption("模型对自己写过的东西也判不准，这条只当参考，别当结论。")


# ---------- 9. 页脚 ----------
st.divider()
st.caption("🇬🇧 地道英语思维训练器 · 测评基于 Beglar & Nation (2007) VST · 数据只保存在本地")
