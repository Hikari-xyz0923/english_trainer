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


# ---------- 2. 初始化数据库 ----------
database.init_db()


# ---------- 3. 页面基础设置 ----------
st.set_page_config(
    page_title="地道英语思维训练器",
    page_icon="🇬🇧",
    layout="wide",
)


# ---------- 3.5 清理 VST 答题状态的小工具 ----------
def clear_vst_state():
    """清空所有 VST 相关的"小抄"（成绩、页码、120道题的选择记录）。
    所有 VST 的 session_state 键都以 vst_ 开头，统一前缀方便一键清除。
    """
    for key in list(st.session_state.keys()):
        if key.startswith("vst_"):
            st.session_state.pop(key, None)


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

tab_analyze, tab_reading = st.tabs(["🔍 句子分析", "📖 阅读营"])


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

    # ---------- 7.1 词汇量测评 ----------
    st.subheader("📏 词汇量测评")
    st.caption(
        "两种模式任选：⚡粗测 5 分钟估区间；🎓完整版 VST 约 15~25 分钟，"
        "基于 Beglar & Nation (2007) 词汇量测试的中文化适配版，给出精确词汇量数字"
    )
    # ---------- ★ 手动填写词汇量（不想做题的快捷通道）----------
    uid = st.session_state["user_id"]
    saved_vocab = database.get_vocab_size(uid)

    with st.expander("✍️ 我知道自己的词汇量（手动填写）"):
        st.caption("不想做 120 题？直接填大致数字。保存后会永久记住（存在数据库里），下次登录不用再填")
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            default_val = int(saved_vocab) if (saved_vocab and str(saved_vocab).isdigit()) else 5000
            manual_vocab = st.number_input(
                "词汇量", min_value=500, max_value=30000, step=100,
                value=default_val, key="manual_vocab_input",
                label_visibility="collapsed",
            )
        with col_btn:
            if st.button("💾 保存", use_container_width=True):
                database.save_vocab_size(uid, manual_vocab)
                st.toast(f"✅ 已记住：约 {manual_vocab:,} 词")
                st.rerun()
        if saved_vocab:
            st.caption(f"📌 当前记住的词汇量：{saved_vocab}（再次保存会覆盖）")
            if st.button("🗑️ 忘掉它，下次重新测评"):
                database.clear_vocab_size(uid)
                st.toast("已清除")
                st.rerun()
    # ---- 结果展示区（测过任何一个模式就在最上面显示）----
    if "vst_result" in st.session_state:
        st.success(
            f"🎓 **VST 完整测评结果：你的词汇量约为 {st.session_state['vst_result']:,} 词**\n\n"
            f"📖 建议阅读难度：根据词汇量选择——4000 以下从 🌱入门 读起，"
            f"4000~8000 选 🌿进阶，8000 以上可挑战 🌳\n\n"
            f"*Based on the Vocabulary Size Test (Beglar & Nation, 2007) · 中文化适配版，结果为估算值*"
        )
        if st.button("🔄 重新测评"):
            st.session_state.pop("vst_result", None)
            clear_vst_state()
            st.rerun()
    elif "vocab_result" in st.session_state:
        level_name, vocab_range, recommend = st.session_state["vocab_result"]
        st.success(f"⚡ **粗测结果：{level_name}**　估算词汇量：{vocab_range}　建议从「{recommend}」难度读起")
        if st.button("🔄 重新测评"):
            st.session_state.pop("vocab_result", None)
            st.rerun()

    st.divider()

    # ---- 模式选择 ----
    quiz_mode = st.radio(
        "选择测评模式：",
        ["⚡ 快速粗测（20 题 · 5 分钟）", "🎓 完整版 VST（120 题 · 15~25 分钟）"],
        horizontal=True,
    )

    # ==================== 模式A：快速粗测 ====================
    if quiz_mode.startswith("⚡"):
        with st.form("vocab_quiz"):
            st.markdown("**按词频分 4 层，每层 5 题**")
            answers = {level: [] for level in ["level1", "level2", "level3", "level4"]}
            for level_key, level_label in [("level1", "第 1 层 · 高频 2000 词"),
                                           ("level2", "第 2 层 · 2000~4000"),
                                           ("level3", "第 3 层 · 4000~8000"),
                                           ("level4", "第 4 层 · 8000+")]:
                st.markdown(f"**{level_label}**")
                for word, options, correct in reading_content.VOCAB_QUIZ[level_key]:
                    answers[level_key].append(
                        st.radio(f"**{word}**", options, index=None, key=f"q_{level_key}_{word}")
                    )
            submitted = st.form_submit_button("交卷，测测我的词汇量", use_container_width=True)

        if submitted:
            all_answers = sum(answers.values(), [])
            if None in all_answers:
                st.warning(f"⚠️ 还有 {all_answers.count(None)} 题没作答，答完再交卷哦～")
            else:
                # 逐层统计答对数：选中的文字 == 正确下标处的文字 即答对
                n = {}
                for level_key in ["level1", "level2", "level3", "level4"]:
                    n[level_key] = sum(
                        1 for i, (w, opts, c) in enumerate(reading_content.VOCAB_QUIZ[level_key])
                        if answers[level_key][i] == opts[c]
                    )
                st.session_state["vocab_result"] = reading_content.estimate_vocab(
                    n["level1"], n["level2"], n["level3"], n["level4"]
                )
                st.rerun()

    # ==================== 模式B：完整版 VST（分层闯关）====================
    else:
        # 先验货：题库必须 120 题齐全才能开考
        if not vst_data.is_complete():
            st.warning(
                f"⚠️ VST 题库还没录满（当前 {vst_data.total_questions()}/120 题），"
                f"先去 vst_data.py 把空着的层补齐，再回来开考～"
            )
            for level in vst_data.VST_LEVELS:
                cnt = len(level["questions"])
                if cnt != 12:
                    st.caption(f"　⬜ {level['label']}：{cnt}/12 题")
        else:
            # 初始化闯关进度（第一次进入时）
            if "vst_page" not in st.session_state:
                st.session_state["vst_page"] = 0        # 当前在第几层（0~9）
                st.session_state["vst_scores"] = {}     # {词段: 答对题数}

            page = st.session_state["vst_page"]
            done = len(st.session_state["vst_scores"])

            st.markdown(f"**闯关进度：已完成 {done}/10 层**")
            st.progress(done / 10)
            st.caption("每答对 1 题 = 掌握 100 个词（统计抽样计分法）。答案会自动保存，可以⬅️回上一层修改")

            level = vst_data.VST_LEVELS[page]
            st.markdown(f"### 当前关卡：{level['label']}")

            with st.form(f"vst_form_{level['band']}"):
                page_answers = []
                for word, options, correct in level["questions"]:
                    page_answers.append(
                        st.radio(f"**{word}**", options, index=None,
                                 key=f"vst_{level['band']}_{word}")
                    )
                level_submitted = st.form_submit_button(
                    "✅ 提交本层，进入下一层" if page < 9 else "🏁 提交最后一层，查看结果",
                    use_container_width=True,
                )

            if level_submitted:
                if None in page_answers:
                    st.warning(f"⚠️ 本层还有 {page_answers.count(None)} 题没作答～")
                else:
                    # 统计本层答对数，存入成绩册
                    n_correct = sum(
                        1 for i, (w, opts, c) in enumerate(level["questions"])
                        if page_answers[i] == opts[c]
                    )
                    st.session_state["vst_scores"][level["band"]] = n_correct

                    # 10 层全交卷 → 计算最终词汇量
                    if len(st.session_state["vst_scores"]) == 10:
                        total_correct = sum(st.session_state["vst_scores"].values())
                        st.session_state["vst_result"] = vst_data.estimate_vst(total_correct)
                        # ★ 自动存档：VST 是精确数字，值得永久记住
                        database.save_vocab_size(st.session_state["user_id"], st.session_state["vst_result"])
                        clear_vst_state()   # 清掉答题过程，只留结果
                    else:
                        if page < 9:
                            st.session_state["vst_page"] += 1
                    st.rerun()

            # 翻页按钮（答案靠 key 自动保留，翻回去还能看到选过的）
            col_prev, col_gap, _ = st.columns([1, 2, 1])
            with col_prev:
                if st.button("⬅️ 上一层", disabled=(page == 0)):
                    st.session_state["vst_page"] -= 1
                    st.rerun()

    st.divider()

        # ---------- 7.2.5 🤖 AI 每日荐读 ----------
    st.subheader("🤖 AI 每日荐读")
    st.caption("根据你的词汇量实时定制 98% 覆盖率的短文——每天都能读到只属于你的 i+1 材料")

    # ★ 先算"有没有词汇量来源"——注意：这行必须在按钮分支外面！
    #   因为它每次运行都要被用到；放在分支里，按钮没点的运行就会 NameError
    has_vocab = (
        "vst_result" in st.session_state
        or "vocab_result" in st.session_state
        or database.get_vocab_size(st.session_state["user_id"]) is not None
    )

    # 生成中锁按钮（key 加标记 → disabled 变灰 → finally 解锁）
    if st.button("✨ 为我生成今日文章", use_container_width=True,
                 disabled=("generating" in st.session_state)):
        if not has_vocab:
            st.warning("⚠️ 先完成词汇量测评，或在上方手动填写词汇量，AI 才知道难度卡在哪～")
        else:
            st.session_state["generating"] = True
            st.rerun()

    # 生成阶段
    if "generating" in st.session_state:
        with st.spinner("🤖 AI 教练正在为你量身定制文章，约 10~20 秒……"):
            try:
                # 取词优先级：本次测评结果 > 数据库里记住的
                if "vst_result" in st.session_state:
                    vocab = st.session_state["vst_result"]          # VST 精确数字
                elif "vocab_result" in st.session_state:
                    vocab = st.session_state["vocab_result"][1]     # 粗测区间
                else:
                    vocab = database.get_vocab_size(st.session_state["user_id"])  # 手填并记住的
                article = glm_api.generate_daily_article(vocab)
                st.session_state["daily_article"] = article
            except Exception as e:
                st.error(f"❌ 生成失败：{e}")
            finally:
                st.session_state.pop("generating", None)   # 无论成败都解锁

    # 展示区
    if "daily_article" in st.session_state:
        with st.container(border=True):
            st.markdown(st.session_state["daily_article"])
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 换一篇（换主题重生成）"):
                st.session_state.pop("daily_article", None)
                st.rerun()
        with col2:
            st.caption("💡 觉得生词太多？该重测词汇量，或去片段图书馆换个更稳的难度")
    st.divider()

    # ---------- 7.3 片段图书馆（内置公版 + AI 无限供货）----------
    st.subheader("📚 片段图书馆")
    st.caption("内置公版名著（经时间审校）+ AI 按你词汇量生成的无限片段（越攒越多，全员共享）")

    source_filter = st.radio("来源", ["全部", "📖 公版名著", "🤖 AI 生成"], horizontal=True)

    # ---- AI 生成入口 ----
    if source_filter != "📖 公版名著":
        ai_vocab = (
            st.session_state.get("vst_result")
            or st.session_state.get("vocab_result", (None, None))[1]
            or database.get_vocab_size(st.session_state["user_id"])
        )
        if st.button("🤖 生成一段新片段", disabled=(ai_vocab is None or "making_passage" in st.session_state)):
            st.session_state["making_passage"] = True
            st.rerun()

        if "making_passage" in st.session_state:
            import random
            from vocabulary_scanner import coverage_report, find_hard_words
            domain = random.choice(glm_api.READING_DOMAINS)   # 复用荐读的领域池！
            with st.spinner(f"🤖 正在创作「{domain}」主题片段……"):
                best_p, best_cov = None, -1    # "历届最佳"：最优片段 + 它的覆盖率
                # ---- 第一阶段：盲写，最多 3 稿，先摸个高分 ----
                for attempt in range(3):
                    try:
                        p = glm_api.generate_library_passage(ai_vocab, domain)
                        cov = coverage_report(p["text"], ai_vocab)["coverage"]
                        st.toast(f"第 {attempt + 1} 稿：覆盖率 {cov}%")
                        if cov > best_cov:
                            best_p, best_cov = p, cov
                        if cov >= 98:
                            break
                    except Exception:
                        continue
                # ---- 第二阶段：批改作文——拿具体生词清单，让 AI 定点降难 ----
                # 盲写摸不到 98% 才启动，最多批改 2 轮
                revise_round = 0
                while best_cov < 98 and revise_round < 2 and best_p is not None:
                    revise_round += 1
                    hard_words = find_hard_words(best_p["text"], ai_vocab)[:10]
                    # 只点名最难的 10 个词——清单太长 AI 会顾此失彼
                    with st.spinner(f"✍️ 第 {revise_round} 轮批改：替换 {len(hard_words)} 个难词……"):
                        try:
                            revised = glm_api.simplify_passage(best_p, hard_words)
                            cov2 = coverage_report(revised["text"], ai_vocab)["coverage"]
                            st.toast(f"批改稿：覆盖率 {cov2}%")
                            if cov2 > best_cov:      # 改得更好才采纳（改砸了保留原稿）
                                best_p, best_cov = revised, cov2
                        except Exception:
                            break                    # 批改环节出错 → 用现有最优稿兜底
                # ---- 上架 ----
                if best_p is None:
                    st.error("❌ 生成失败，点「生成」再试一次")
                else:
                    database.save_passage(best_p["title"], best_p["level"], domain,
                                          best_p["intro"], best_p["text"],
                                          best_p["expressions"],
                                          st.session_state["user_id"])
                    if best_cov >= 98:
                        st.toast(f"✅ 已上架！覆盖率 {best_cov}%")
                    elif best_cov >= 90:
                        st.warning(f"已上架（覆盖率 {best_cov}%）——接近但没到 98%，"
                                   f"读时配合生词清单效果依然很好")
                    else:
                        st.warning(f"已上架最优稿（覆盖率 {best_cov}%）——偏难，"
                                   f"建议先背生词清单再读")
            st.session_state.pop("making_passage", None)
        if ai_vocab is None:
            st.caption("⚠️ 先完成词汇量测评或手动填写，AI 才知道片段难度怎么定")
        if ai_vocab is None:
            st.caption("⚠️ 先完成词汇量测评或手动填写，AI 才知道片段难度怎么定")
        if ai_vocab is None:
            st.caption("⚠️ 先完成词汇量测评或手动填写，AI 才知道片段难度怎么定")

    # ---- 展示区：公版片段 ----
    if source_filter in ("全部", "📖 公版名著"):
        st.markdown("**📖 公版名著（人类经典）**")
        level_filter = st.radio("难度", ["全部", "🌱 入门", "🌿 进阶", "🌳 挑战"],
                                horizontal=True, key="classic_level")
        for p in reading_content.PASSAGES:
            if level_filter != "全部" and p["level"] != level_filter:
                continue
            with st.expander(f"#{p['id']} {p['title']}"):
                st.caption(f"{p['author']} · {p['level']}")
                st.markdown(f"*{p['intro']}*")
                st.markdown(p["text"])
                with st.expander("💎 值得收编的表达"):
                    for expr in p["expressions"]:
                        st.markdown(f"- {expr}")
                        
    # ---- 展示区：AI 片段 ----
    if source_filter in ("全部", "🤖 AI 推荐名著"):
        passages = database.get_all_passages()
        st.markdown(f"**🤖 AI 推荐名著（已入库 {len(passages)} 段）**")
        if len(passages) == 0:
            st.info("AI 仓库还是空的——点上方「生成一段新片段」，成为第一个供货人！")
        for pid, title, level, domain, intro, text, exprs, words, created_at in passages:
            with st.expander(f"#{pid} {title}"):
                st.caption(f"{level} · 领域:{domain} · 约{words}词 · {created_at}")
                st.markdown(f"*{intro}*")
                st.markdown(text)
                with st.expander("💎 值得收编的表达"):
                    for expr in exprs.split("\n"):
                        st.markdown(f"- {expr}")
                                    # ---- 覆盖率体检：数据说话，这段文本适不适合你？ ----
            from vocabulary_scanner import coverage_report
            report = coverage_report(text, ai_vocab)   # ai_vocab = 前面算好的读者词汇量

            
                        # ---- 覆盖率徽章（五档精细化评级）----
            cov = report["coverage"]
            hard_info = f"｜生词 {report['hard_count']} 个（出现 {report['hard_hits']} 次）"
            if cov > 98:
                st.success(f"🔬 覆盖率 {cov}% 🌟 完美！纯享受式阅读"
                           f"｜生词仅 {report['hard_count']} 个（出现 {report['hard_hits']} 次）")
            elif cov > 97:
                st.success(f"🔬 覆盖率 {cov}% ✅ 达到 98% 可理解输入标准附近，放心读{hard_info}")
            elif cov > 95:
                st.info(f"🔬 覆盖率 {cov}% 👍 良好——主线剧情毫无压力，"
                        f"少量生词正是学习材料{hard_info}")
            elif cov > 92:
                st.warning(f"🔬 覆盖率 {cov}% ⚠️ 有挑战——建议先浏览下方生词清单再读{hard_info}")
            else:
                st.error(f"🔬 覆盖率 {cov}% ❌ 偏难——推荐先背生词清单，或换一篇更简单的{hard_info}")
            # 生词清单 + 一键全收编
            with st.expander(f"🔍 本篇生词清单（{report['hard_count']} 个）"):
                if report["hard_count"] == 0:
                    st.info("全篇无生词——这对你来说是纯复习材料，放心读！")
                else:
                    # 生词逐个列出：词 + 难度分（分越低越罕见）
                    for w, s in report["unique_hard"]:
                        st.markdown(f"- **{w}**（Zipf {s}）")
                    # 一键收编：把整份生词清单存进个人生词本
                    if st.button(f"💎 一键收编全部 {report['hard_count']} 个生词",
                                 key=f"collect_{pid}"):
                        ok, dup = 0, 0
                        for w, s in report["unique_hard"]:
                            # 收编时带上出处（哪篇片段），meaning 留空等用户补
                            if database.add_collected_word(
                                st.session_state["user_id"], w, "", title
                            ):
                                ok += 1
                            else:
                                dup += 1              # 生词本里已有的算重复
                        st.toast(f"收编 {ok} 个新词{('，' + str(dup) + ' 个已在本子里') if dup else ''} 💎")
                        st.rerun()
                # 👇👇 从这里开始是新增的删除区（和上面的 with 同级缩进）👇👇
            with st.expander("🗑️ 管理这篇片段"):
                # 二次确认：第一次点只"亮红灯"，第二次点才真删
                if st.session_state.get(f"confirm_del_{pid}", False):
                    st.warning("⚠️ 真的要删除吗？删除后无法恢复！")
                    col1, col2 = st.columns(2)
                    if col1.button("确认删除", key=f"del_yes_{pid}"):
                        n = database.delete_passage(pid)   # 接住战果：实际删中几行
                        st.toast(f"试图删除 #{pid}，删中 {n} 行 🗑️")   # 行车记录仪
                        del st.session_state[f"confirm_del_{pid}"]  # 清除确认状态
                        st.rerun()                                # 重画页面        # 重画页面
                    if col2.button("手滑了，取消", key=f"del_no_{pid}"):
                        del st.session_state[f"confirm_del_{pid}"]
                        st.rerun()
                else:
                    if st.button("删除这篇片段", key=f"del_{pid}"):
                        st.session_state[f"confirm_del_{pid}"] = True
                        st.rerun()
            
    # ==================== 7.4 我的生词本 ====================
    st.subheader("📖 我的生词本")
    my_words = database.get_collected_words(st.session_state["user_id"])
    if len(my_words) == 0:
        st.info("生词本还是空的——在上方片段里点「💎 一键收编」，词汇积累从现在开始！")
    else:
        st.caption(f"已积累 {len(my_words)} 个表达。点击展开查看详情。")
        for wid, expr, meaning, source, met_count, created_at in my_words:
            with st.expander(f"💎 {expr}" + (f"（{meaning}）" if meaning else "")):
                st.caption(f"收编于 {created_at} ｜ 出处：{source}")
                # 数据库里存过的（上次补课的成果）直接展示
                if meaning:
                    st.markdown(f"**义项：**{meaning}")
                if met_count:
                    pass  # met_count 留给 12 次重遇引擎，先占位
                # ---- AI 补课按钮 ----
                if st.button("🤖 AI 补课", key=f"teach_{wid}"):
                    with st.spinner(f"正在为「{expr}」备课……"):
                        try:
                            notes = glm_api.get_word_notes([(expr, 0.0)])
                            note = notes.get(expr.lower(), {})
                            if note:
                                # 拼纯文本存数据库（meaning 存义项，usage 存词形+例句）
                                new_meaning = "；".join(note.get("senses", []))
                                usage_lines = []
                                if note.get("forms"):
                                    usage_lines.append(f"词形：{note['forms']}")
                                for i, (en, zh) in enumerate(note.get("examples", []), 1):
                                    usage_lines.append(f"例{i}：{en}（{zh}）")
                                new_usage = "\n".join(usage_lines)
                                database.update_word_notes(wid, st.session_state["user_id"],
                                                           new_meaning, new_usage)
                                # 全卡缓存进 session_state，本次页面立刻可看
                                st.session_state[f"card_{wid}"] = note
                                st.toast(f"「{expr}」补课完成 💎")
                                st.rerun()
                            else:
                                st.warning("AI 没返回有效讲解，再点一次试试")
                        except Exception as e:
                            st.error(f"补课失败：{e}")

                # ---- 全息词卡展示（优先用本次会话刚补的课，数据库的 meaning 已在 expander 标题/上方展示）----
                card = st.session_state.get(f"card_{wid}", None)
                if card:
                    if card.get("forms") and card["forms"] != "无变化":
                        st.markdown(f"**词形：**{card['forms']}")
                    if card.get("senses"):
                        st.markdown("**义项：**" + "；".join(card["senses"]))
                    for i, (en, zh) in enumerate(card.get("examples", []), 1):
                        st.markdown(f"**例{i}：**{en}")
                        st.caption(zh)
                # 补课成功后，本次会话内直接展示新释义（不等下次刷新）
                if st.session_state.get(f"meaning_{wid}", ""):
                    st.info(f"🤖 刚补的课——释义：{st.session_state[f'meaning_{wid}']}")
                if meaning:
                    st.markdown(f"**释义：**{meaning}")
                if st.button("移出本子", key=f"rm_word_{wid}"):
                    database.delete_collected_word(wid, st.session_state["user_id"])
                    st.toast(f"已移出 {expr}")
                    st.rerun()
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

    # 退出登录：连测评状态一起清干净，防止下一个人看到上一个人的答案
    if st.button("🚪 退出登录", use_container_width=True):
        for key in ["user_id", "username", "last_input", "last_analysis",
                    "review_record", "vocab_result", "vst_result"]:
            st.session_state.pop(key, None)
        clear_vst_state()
        st.rerun()


# ---------- 9. 页脚 ----------
st.divider()
st.caption("🇬🇧 地道英语思维训练器 · 测评基于 Beglar & Nation (2007) VST · 数据只保存在本地")