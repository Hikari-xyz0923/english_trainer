# -*- coding: utf-8 -*-
"""成长历程 / 今日任务 —— 顶部四张卡点进来的两个独立界面。

为什么单独成"界面"而不是再加两个 tab：
  tab 栏已经有四个了，再加就横向拉不完，而且这两个是"回头看一眼"的页面，
  不该和每天都在用的练习并列。

为什么用 session_state 切视图、不用 ?view= 跳链接：
  Streamlit 里 HTML 的 <a href="?view=growth"> 会让浏览器整页重载，
  session_state 全清空——刚分析完的句子、刚生成的片段都会没。
  改 session_state 只是让脚本重跑一遍，界面瞬间换，状态一个不丢。

数据来源：全部来自已有的 point_logs / checkin_records 两张表。
  没有任何新的埋点，也就是"过去攒的分自动变成了这里的图"。
"""

import datetime
import html

import streamlit as st

import database
import rank_system
import ui_theme

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


# ============================================================
# 公共零件
# ============================================================

def _page_head(title, sub):
    """页头：左边返回按钮，右边标题；副标题单独一行。"""
    c1, c2 = st.columns([1, 6], vertical_alignment="center")
    with c1:
        st.button("← 回到练习", key="back_home",
                  on_click=ui_theme.switch_view, args=("home",))
    with c2:
        st.markdown(f'<div class="page-title">{html.escape(title)}</div>',
                    unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">{html.escape(sub)}</div>',
                unsafe_allow_html=True)


# ============================================================
# 界面一：成长历程
# ============================================================

def render_growth(user_id):
    """段位阶梯 + 当前大段进度 + 积分流水 + 打卡日历。"""
    _page_head(
        "📈 成长历程",
        "段位只是积分的另一种写法。这里看三件事：走到哪了、分是怎么来的、哪天断了。",
    )

    pts = database.get_total_points(user_id)
    rank = rank_system.points_to_rank(pts)
    streak = database.get_checkin_streak(user_id)
    total_ck = database.get_total_checkins(user_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("当前段位", rank["rank_name"])
    c2.metric("总积分", f"{pts}")
    c3.metric("连续打卡", f"{streak} 天")
    c4.metric("累计打卡", f"{total_ck} 天")

    st.write("")
    _rank_ladder(rank)

    # ---- 当前大段内的进度 ----
    span = max(rank["seg_end"] - rank["seg_start"], 1)
    into = max(pts - rank["seg_start"], 0)
    st.progress(
        min(into / span, 1.0),
        text=f"{rank['sub_name']} · 本段已走 {into} / {span} 分",
    )
    if rank["next_need"] is None:
        st.caption("👑 已到最高段位，没有下一站了。")
    elif rank["next_need"] <= 20:
        st.caption(f"还差 **{rank['next_need']} 分**就升级——今天打卡一次就够。")
    else:
        # 一天做满是多少分，从 TASKS 现算——写死 25 的话，加一项任务就会对不上
        daily_max = sum(t[2] for t in TASKS)
        st.caption(
            f"还差 **{rank['next_need']} 分**升级。"
            f"按每天把 {len(TASKS)} 项任务做满（约 {daily_max} 分）算，"
            f"大概 {max(1, round(rank['next_need'] / daily_max))} 天。"
        )

    st.divider()

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        _point_logs(user_id)
    with right:
        _checkin_calendar(user_id)


def _rank_ladder(rank):
    """七个大段横向排开，走过的实心、当前的高亮、没到的灰着。

    为什么画这个而不是再放一个进度条：
      进度条只回答"还差多少"，日历式的阶梯才回答"我离终点有多远"。
      七段一屏看得完，是最省地方的全局视图。
    """
    st.markdown("**段位阶梯**")
    node_count = len(rank_system.RANKS)
    parts = []
    for i, r in enumerate(rank_system.RANKS):
        emoji, _, name = r["name"].partition(" ")
        cls = "rank-node"
        if i < rank["rank_index"]:
            cls += " done"
        elif i == rank["rank_index"]:
            cls += " now"
        parts.append(
            f'<div class="{cls}">'
            f'<span class="dot">{html.escape(emoji)}</span>'
            f'<span class="nm">{html.escape(name)}</span>'
            f'<span class="th">{r["threshold"]} 分起</span>'
            f"</div>"
        )
        if i < node_count - 1:
            line_cls = "rank-line done" if i < rank["rank_index"] else "rank-line"
            parts.append(f'<div class="{line_cls}"></div>')
    st.markdown(f'<div class="rank-ladder">{"".join(parts)}</div>',
                unsafe_allow_html=True)


def _point_logs(user_id, limit=14):
    """积分流水：每一笔分都能追溯到"哪天干了什么"。"""
    st.markdown("**积分流水**")
    logs = database.get_point_logs(user_id, limit)
    if not logs:
        st.caption("还没有积分记录。打卡一次就有了。")
        return

    rows = []
    for amount, reason, created in logs:
        # created 形如 '2026-11-01 15:42:31'，只显示到分钟
        when = html.escape(str(created)[5:16])
        sign = "+" if amount >= 0 else ""
        cls = "log-a" if amount >= 0 else "log-a neg"
        rows.append(
            f'<div class="log-row">'
            f'<span class="log-t">{when}</span>'
            f'<span class="log-r">{html.escape(str(reason))}</span>'
            f'<span class="{cls}">{sign}{int(amount)}</span>'
            f"</div>"
        )
    st.markdown(f'<div class="log">{"".join(rows)}</div>', unsafe_allow_html=True)
    st.caption(f"只显示最近 {len(logs)} 笔。同一任务每天只发一次分，所以这里不会出现重复。")

    # 分项合计：让人一眼看出哪类活动贡献最大
    total = sum(int(a) for a, _, _ in logs)
    st.caption(f"这 {len(logs)} 笔合计 {total} 分。")


def _checkin_calendar(user_id, weeks=5):
    """最近五周的打卡日历，按周一到周日对齐。

    为什么按星期对齐而不是简单排成 7 列：
      对齐之后"我总在周末断"这种模式才看得出来，
      只是顺序填充的话，每个格子对应的星期几每周都不一样，看不出来。
    """
    st.markdown("**打卡日历**")
    done = database.get_checkin_dates(user_id, weeks * 7 + 6)
    today = datetime.date.today()
    start = today - datetime.timedelta(days=weeks * 7 - 1)
    start -= datetime.timedelta(days=start.weekday())      # 退到那一周的周一

    cells = [f'<div class="cal-head">{w}</div>' for w in WEEKDAY_CN]
    d = start
    while d <= today:
        cls = "cal-cell"
        if d.isoformat() in done:
            cls += " on"
        if d == today:
            cls += " today"
        cells.append(f'<div class="{cls}" title="{d.isoformat()}"></div>')
        d += datetime.timedelta(days=1)

    st.markdown(f'<div class="cal">{"".join(cells)}</div>', unsafe_allow_html=True)
    st.caption(f"深色 = 打过卡，右下角描边那格是今天。最近 {weeks} 周共打卡 {len(done)} 天。")


# ============================================================
# 界面二：今日任务
# ============================================================

# (图标, 名称, 分值, 怎么完成)
# 分值必须和 app.py 侧边栏里实际发分的地方一致，不然这里就是骗人的。
TASKS = [
    ("📅", "每日打卡", 10, "在侧边栏点「今日打卡」"),
    ("🧠", "完成 1 次句子分析", 5, "去「🔍 句子分析」随便写一句英文"),
    ("💎", "收编 1 个生词", 2, "分析结果里点「收编」存进生词本"),
    ("📖", "阅读 1 篇 AI 片段", 8, "去「📖 阅读营」打开一篇并读完"),
    ("🔁", "复习一组生词", 3, "去「📖 阅读营 → 生词本」点「开始复习」"),
]

# 任务名 → 查"今天做没做"用的 point_logs.reason
TASK_REASONS = [None, "完成句子分析", "收编生词", "阅读片段", "复习生词"]


def render_quests(user_id):
    """今日任务 + 近七天得分 + 加分规则。"""
    _daily_total = sum(t[2] for t in TASKS)
    _page_head(
        "🎯 今日任务",
        f"{len(TASKS)} 项做完一共 {_daily_total} 分。"
        "清单每天零点自动重置——断了不可惜，明天再来。",
    )

    checked_today = database.has_checked_in_today(user_id)
    streak = database.get_checkin_streak(user_id)

    done_flags = [checked_today]
    for reason in TASK_REASONS[1:]:
        done_flags.append(database.task_done_today(user_id, reason))

    done_count = sum(1 for f in done_flags if f)
    total_reward = sum(t[2] for t in TASKS)

    # ---- 顶部：今日进度 ----
    st.progress(done_count / len(TASKS), text=f"今日完成 {done_count}/{len(TASKS)}")
    if done_count == len(TASKS):
        st.success(f"🎉 今天 {total_reward} 分全拿到了，书虫饱了。")
    else:
        missing = total_reward - sum(t[2] for t, f in zip(TASKS, done_flags) if f)
        st.caption(f"还差 {len(TASKS) - done_count} 项，还有 {missing} 分可以拿。")

    st.write("")

    # ---- 任务卡 ----
    parts = []
    for (icon, name, reward, tip), is_done in zip(TASKS, done_flags):
        cls = "quest done" if is_done else "quest"
        parts.append(
            f'<div class="{cls}">'
            f'<span class="quest-ico">{icon}</span>'
            f'<span class="quest-body">'
            f'<span class="quest-name">{html.escape(name)}</span>'
            f'<span class="quest-tip">{html.escape(tip)}</span>'
            f"</span>"
            f'<span class="quest-pri">+{reward} 分</span>'
            f'<span class="quest-st">{"已完成" if is_done else "待完成"}</span>'
            f"</div>"
        )
    # quest-name / quest-tip 是块级视觉，span 强制成块
    st.markdown(
        f'<style>.quest-body .quest-name,.quest-body .quest-tip{{display:block;}}</style>'
        f'<div>{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )

    # ---- 连击奖励提示 ----
    if streak >= 30:
        st.caption(f"🔥 连击 {streak} 天，打卡额外 +15 分已经在发了。")
    elif streak >= 3:
        st.caption(f"🔥 连击 {streak} 天，打卡额外 +5 分。撑到 30 天变成 +15。")
    elif streak >= 1:
        st.caption(f"🔥 连击 {streak} 天。连到第 3 天起，每次打卡多拿 5 分。")
    else:
        st.caption("🔥 连击还没开始。今天打卡一次就从 1 天起算。")

    st.divider()

    # ---- 近七天得分 ----
    _week_bars(user_id)

    st.divider()

    # ---- 加分规则 ----
    st.markdown("**加分规则**")
    st.markdown(
        "- 📅 每日打卡 **+10**（连击 ≥3 天 **+5**，≥30 天 **+15**）\n"
        "- 🧠 完成 1 次句子分析 **+5**\n"
        "- 💎 收编 1 个生词 **+2**\n"
        "- 📖 阅读 1 篇片段 **+8**\n"
    )
    st.caption(
        "除打卡外，每项每天只发一次分——多写不叠加。"
        "这一条是故意的：这个软件要的是「每天都来」，不是「一次刷到宗师」。"
    )


def _week_bars(user_id, days=7):
    """近七天每天拿了多少分。断签的日子会显示成空条。"""
    st.markdown("**近七天得分**")
    by_day = database.get_points_by_day(user_id, days)
    today = datetime.date.today()

    # 满格基准取"实际最高"和 25（一天的满额）里较大的那个，
    # 否则某天爆了 80 分之后，其余每天的条都会缩成一小截。
    peak = max(list(by_day.values()) + [25])

    rows = []
    for i in range(days - 1, -1, -1):
        d = today - datetime.timedelta(days=i)
        key = d.isoformat()
        p = by_day.get(key, 0)
        width = max(p / peak * 100, 2) if p else 0
        label = "今天" if i == 0 else f"{d.month}/{d.day} 周{WEEKDAY_CN[d.weekday()]}"
        p_cls = "week-p" if p else "week-p zero"
        rows.append(
            f'<div class="week-row">'
            f'<span class="week-d">{label}</span>'
            f'<span class="week-bar"><span class="week-fill" style="width:{width:.1f}%"></span></span>'
            f'<span class="{p_cls}">{p} 分</span>'
            f"</div>"
        )
    st.markdown(f'<div class="week">{"".join(rows)}</div>', unsafe_allow_html=True)

    hit = sum(1 for k in by_day if k)
    st.caption(f"最近七天有 {hit} 天拿到过分。空条不代表没学，只代表那天没触发这几项。")
