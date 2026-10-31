# -*- coding: utf-8 -*-
# ============================================================
# 阅读营 —— 四个子页面（从 app.py 原第 7 节原样拆出，逻辑未改，只加分层导航）
#   render_vocab    📏 词汇量测评（⚡粗测 / 🎓VST 闯关 / ✍️手动填写）
#   render_daily    🤖 AI 每日荐读
#   render_library  📚 片段图书馆（公版名著 + AI 生成）
#   render_words    📖 我的生词本
# ============================================================
import streamlit as st

import database
import glm_api
import reading_content
import vst_data


def clear_vst_state():
    """清空所有 VST 相关的 session_state（app.py 的退出登录也用这份）。"""
for key in list(st.session_state.keys()):
    if key.startswith("vst_"):
        st.session_state.pop(key, None)



def render_vocab():
    """📏 词汇测评 子页。"""

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


def render_daily():
    """🤖 每日荐读 子页。"""

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


def render_library():
    """📚 片段图书馆 子页。"""

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
                last_err = None                # 记下最后一稿为什么失败，别再让界面只说一句"生成失败"
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
                    except Exception as e:
                        last_err = e
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
                    st.error(f"❌ 生成失败：{last_err if last_err is not None else '未知原因'}")
                    st.caption("连续 3 稿都没成功。上面的报错末尾通常是状态码："
                               "401 = Key 不对或已失效，429 = 额度用尽，"
                               "400/404 = 模型名不可用。")
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
    if source_filter in ("全部", "🤖 AI 生成"):
        passages = database.get_all_passages()
        st.markdown(f"**🤖 AI 生成片段（已入库 {len(passages)} 段）**")
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
                        database.award_once_today(st.session_state["user_id"], 2, "收编生词")
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


def render_words():
    """📖 生词本 子页。"""

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
