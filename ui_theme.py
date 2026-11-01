# ============================================================
# ui_theme.py —— 视觉层：全局 CSS + 顶部状态条
#
# 为什么单独一个文件：
#   app.py 已经有 470 行业务逻辑，再把 200 行 CSS 塞进去就没法读了。
#   这里只做两件事——注入样式、渲染顶部那块"今天的我"。
#
# 设计约束（踩过的坑，别改）：
#   ① 不硬设整页背景色。背景交给 .streamlit/config.toml 的 [theme]，
#      CSS 只改字体、圆角、间距、按钮、tab。这样换主题时不会崩。
#   ② 不碰 Streamlit 的内部类名（.st-emotion-cache-xxxx 会随版本变），
#      只用 data-testid 和语义选择器。
#   ③ 所有用户输入的内容必须 html.escape，否则用户名里带 < 就能注入标签。
# ============================================================

import html

import streamlit as st

BASE_CSS = """
<style>
:root{
  --ink:#1A1A18;
  --muted:#6B6B63;
  --line:rgba(26,26,24,.11);
  --brand:#1F6F5C;
  --brand-soft:rgba(31,111,92,.09);
  --card:#FFFFFF;
  --radius:10px;
}

/* ---- 字体：中文优先用系统黑体，避免 Streamlit 默认字体把中文渲染得很散 ---- */
/* ★ 这里必须排除图标元素（data-testid="stIconMaterial"）。
   图标 span 里装的不是文字，是连字名（"arrow_down"、"keyboard_arrow_down"），
   靠 "Material Symbols Rounded" 字体的 ligature 把单词渲染成图形。
   一旦被换成普通字体，ligature 失效，页面上就把 "arrow_down" 当单词画出来——
   每个折叠面板标题前面叠着的那个 "_arrow_down" 就是这个原因。 */
html, body, [class*="st-"]:not([data-testid="stIconMaterial"]):not([class*="material-symbols"]){
  font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
              "Hiragino Sans GB", "Microsoft YaHei", "Source Han Sans SC", sans-serif;
}

/* 图标字体兜底：即便有别的规则误伤，也把图形字体抢回来 */
[data-testid="stIconMaterial"],
[class*="material-symbols"]{
  font-family:"Material Symbols Rounded" !important;
  font-weight:normal !important;
  font-style:normal !important;
  letter-spacing:normal !important;
  text-transform:none !important;
  line-height:1 !important;
  white-space:nowrap;
  direction:ltr;
  -webkit-font-smoothing:antialiased;
  -webkit-font-feature-settings:"liga";
  font-feature-settings:"liga";
}

/* ---- 版心：默认太宽，正文行长超过 100 字符就很难读 ---- */
/* ★ Streamlit 1.62 把主容器 testid 从 stAppViewBlockContainer 改成了
   stMainBlockContainer。写旧名字的话这条规则静默失效（不报错、也不生效），
   版心会退回默认 750px——第一版就是这样白改的。两个都写上，兼容旧版。 */
[data-testid="stMainBlockContainer"],
[data-testid="stAppViewBlockContainer"]{
  padding-top:2.4rem; padding-bottom:3rem; max-width:1040px;
}
[data-testid="stHeader"]{ background:transparent; }

/* ---- 标题层级：Streamlit 默认 h1 太轻、h2/h3 太挤 ---- */
h1{ font-weight:600 !important; font-size:1.85rem !important; letter-spacing:-.02em; }
h2{ font-weight:600 !important; font-size:1.3rem !important; letter-spacing:-.01em; }
h3{ font-weight:600 !important; font-size:1.05rem !important; }

/* ---- tab：默认是带下划线的方标签，改成胶囊（更像产品不像后台） ---- */
/* ★ 1.62 去掉了 baseweb，tab 的 DOM 变成 role="tablist" + [data-testid="stTab"]。
   原来写 [data-baseweb="tab"] 一个都匹配不到，胶囊化从来没生效过。
   选中态靠 aria-selected，不是 [aria-selected] 里的 arbitrary value。 */
[data-testid="stTabs"] [role="tablist"]{
  gap:6px; border-bottom:none;
}
[data-testid="stTab"]{
  height:34px; padding:0 14px !important; border-radius:999px;
  color:var(--muted); font-weight:500;
  transition:background .15s ease, color .15s ease;
}
[data-testid="stTab"]:hover{ background:rgba(26,26,24,.04); }
[data-testid="stTab"][aria-selected="true"]{
  background:var(--brand-soft);
}
[data-testid="stTab"][aria-selected="true"] p{
  color:var(--brand) !important; font-weight:600;
}
/* 选中项下面那条横线（1.62 用伪元素/边框实现，一并压掉） */
[data-testid="stTab"][aria-selected="true"]::after{ display:none !important; }

/* ---- 按钮：默认直角、无 hover 反馈 ---- */
/* 用 data-testid 定位：.stButton > button 在 1.62 只匹配到一部分
   （按钮外面多套了一层 div，不再是直接子级） */
[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button,
[data-testid="stFormSubmitButton"] button{
  border-radius:8px; border:1px solid var(--line); font-weight:500;
  padding:.48rem 1rem; transition:border-color .15s ease, color .15s ease;
}
[data-testid="stButton"] button:hover,
[data-testid="stDownloadButton"] button:hover{
  border-color:var(--brand); color:var(--brand);
}
[data-testid="stButton"] button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"]{
  background:var(--brand); border-color:var(--brand); color:#fff;
}
[data-testid="stButton"] button[kind="primary"]:hover{
  color:#fff; border-color:var(--brand); opacity:.92;
}

/* ---- 容器与折叠面板 ---- */
[data-testid="stExpander"]{
  border:1px solid var(--line); border-radius:var(--radius);
  background:var(--card); overflow:hidden;
}
[data-testid="stExpander"] summary{ font-weight:500; }

/* ---- 指标卡 ---- */
[data-testid="stMetric"]{
  background:var(--card); border:1px solid var(--line);
  border-radius:var(--radius); padding:14px 16px;
}
[data-testid="stMetricValue"]{ font-size:1.45rem; }
[data-testid="stMetricLabel"]{ color:var(--muted); }

/* ---- 杂项：分割线太黑、输入框直角 ---- */
hr{ margin:1.5rem 0 !important; border-color:var(--line) !important; }
[data-testid="stTextArea"] textarea,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
.stTextArea textarea, .stTextInput input, .stNumberInput input{
  border-radius:8px !important;
}
[data-testid="stSidebar"]{ border-right:1px solid var(--line); }
[data-testid="stSidebar"] h1{ font-size:1.1rem !important; }
[data-testid="stSidebar"] hr{ margin:1rem 0 !important; }

/* ---- 顶部状态条（hero）----
   ★ 改造说明：原来这四张卡是一整块 HTML，好看但点不了——
     Streamlit 的 HTML 里塞 <a href="?view=..."> 会触发整页重载，
     刚分析完的句子、刚生成的片段全会丢。
     现在改成 st.container + 真按钮：点击只是 session_state 变一下，
     界面瞬间切换，状态一个不丢。CSS 负责把它们伪装成原来的卡片。

   ★ 选择器说明：1.62 里 st.container(border=True) 不再包一层
     stVerticalBlockBorderWrapper，border 直接画在 stVerticalBlock 上。
     所以改用「直接子级里有 stElementContainer、且后代含 .hero-anchor 的
     stVerticalBlock」来定位，避免误伤外层容器。 */
[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .hero-anchor){
  background:var(--card);
  border:1px solid var(--line) !important;
  border-left:3px solid var(--brand) !important;
  border-radius:var(--radius) !important;
  padding:16px 20px 14px !important;
  margin-bottom:20px;
}
.hero-anchor{ display:none; }

.hero-title{ font-size:1.32rem; font-weight:600; color:var(--ink); letter-spacing:-.01em; }
.hero-sub{ font-size:.86rem; color:var(--muted); margin-top:5px; }

/* 四张卡的小标签（段位/积分/连击/今日任务） */
[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .hero-anchor) [data-testid="stCaptionContainer"]{
  margin:0 0 3px 3px; min-height:0;
}
[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .hero-anchor) [data-testid="stCaptionContainer"] p{
  font-size:.7rem; color:var(--muted); letter-spacing:.06em; line-height:1.2;
}

/* 卡片本体：把所有 key 以 hero_ 开头的按钮做成 chip */
[class*="st-key-hero_"] button{
  background:#F7F5EF !important;
  border:1px solid var(--line) !important;
  color:var(--ink) !important;
  font-weight:600 !important; font-size:.93rem !important;
  border-radius:8px !important; min-height:2.15rem; padding:0 .45rem !important;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  transition:border-color .15s ease, background .15s ease, color .15s ease;
}
[class*="st-key-hero_"] button:hover{
  border-color:var(--brand) !important; color:var(--brand) !important; background:#fff !important;
}
/* 第四张（今日任务）用主题色，跟其他三张区分开 */
.st-key-hero_quests button{
  background:var(--brand-soft) !important;
  border-color:rgba(31,111,92,.22) !important;
  color:var(--brand) !important;
}
.st-key-hero_quests button:hover{ background:rgba(31,111,92,.16) !important; }

/* ---- 独立界面（成长历程 / 今日任务）的页头 ---- */
.page-head{ margin:2px 0 2px; }
.page-title{ font-size:1.42rem; font-weight:600; color:var(--ink); letter-spacing:-.01em; }
.page-sub{ font-size:.85rem; color:var(--muted); margin-top:4px; margin-bottom:18px; }

/* ---- 段位阶梯：七个大段横向排开 ---- */
.rank-ladder{
  display:flex; align-items:flex-start; gap:0;
  padding:14px 4px 6px; overflow-x:auto;
}
.rank-node{ flex:none; width:92px; text-align:center; opacity:.45; }
.rank-node.done{ opacity:.8; }
.rank-node.now{ opacity:1; }
.rank-node .dot{
  display:block; width:36px; height:36px; line-height:36px; margin:0 auto 6px;
  border-radius:50%; background:#F1EFE8; font-size:1.05rem;
  transition:background .2s ease;
}
.rank-node.done .dot{ background:var(--brand-soft); }
.rank-node.now .dot{ background:var(--brand); box-shadow:0 0 0 4px rgba(31,111,92,.13); }
.rank-node .nm{ display:block; font-size:.73rem; color:var(--ink); }
.rank-node.now .nm{ color:var(--brand); font-weight:600; }
.rank-node .th{ display:block; font-size:.65rem; color:var(--muted); margin-top:2px; }
.rank-line{ flex:1; height:2px; background:var(--line); margin-top:17px; min-width:10px; }
.rank-line.done{ background:rgba(31,111,92,.38); }

/* ---- 积分流水 ---- */
.log{ border:1px solid var(--line); border-radius:var(--radius); overflow:hidden; }
.log-row{
  display:flex; align-items:center; gap:12px; padding:9px 14px;
  border-bottom:1px solid var(--line); font-size:.85rem;
}
.log-row:last-child{ border-bottom:none; }
.log-row:nth-child(even){ background:#FCFBF8; }
.log-t{
  width:132px; flex:none; color:var(--muted);
  font-variant-numeric:tabular-nums; font-size:.78rem;
}
.log-r{ flex:1; color:var(--ink); }
.log-a{
  width:56px; flex:none; text-align:right; font-weight:600; color:var(--brand);
  font-variant-numeric:tabular-nums;
}
.log-a.neg{ color:#B4453A; }

/* ---- 打卡日历 ---- */
.cal{ display:grid; grid-template-columns:repeat(7, 1fr); gap:6px; max-width:330px; }
.cal-head{ font-size:.67rem; color:var(--muted); text-align:center; letter-spacing:.04em; }
.cal-cell{ aspect-ratio:1 / 1; border-radius:5px; background:#F1EFE8; }
.cal-cell.on{ background:var(--brand); }
.cal-cell.today{ box-shadow:0 0 0 2px rgba(31,111,92,.35); }
.cal-cell.future{ background:transparent; }

/* ---- 任务卡 ---- */
.quest{
  display:flex; align-items:center; gap:14px; padding:13px 16px; margin-bottom:9px;
  border:1px solid var(--line); border-radius:var(--radius); background:var(--card);
  transition:border-color .15s ease;
}
.quest.done{ background:var(--brand-soft); border-color:rgba(31,111,92,.22); }
.quest-ico{ font-size:1.25rem; width:30px; flex:none; text-align:center; }
.quest-body{ flex:1; min-width:0; }
.quest-name{ font-size:.92rem; color:var(--ink); font-weight:500; }
.quest.done .quest-name{ color:var(--brand); }
.quest-tip{ font-size:.74rem; color:var(--muted); margin-top:3px; }
.quest-pri{ flex:none; font-size:.8rem; font-weight:600; color:var(--brand); }
.quest-st{ flex:none; font-size:.78rem; color:var(--muted); width:52px; text-align:right; }
.quest.done .quest-st{ color:var(--brand); }

/* ---- 近七天得分 ---- */
.week{ display:flex; flex-direction:column; gap:7px; margin-top:6px; }
.week-row{ display:flex; align-items:center; gap:10px; font-size:.8rem; }
.week-d{ width:78px; flex:none; color:var(--muted); font-variant-numeric:tabular-nums; }
.week-bar{ flex:1; height:13px; background:#F1EFE8; border-radius:4px; overflow:hidden; }
.week-fill{
  display:block;              /* ★ span 默认是 inline，inline 元素的 width/height 会被忽略，
                                 结果就是"条永远是空的、但右边的分数是对的" */
  height:100%; background:var(--brand); border-radius:4px;
}
.week-p{
  width:56px; flex:none; text-align:right; color:var(--ink);
  font-variant-numeric:tabular-nums;
}
.week-p.zero{ color:#B0AEA6; }

/* ---- 间隔重复：复习卡 ---- */
.srs-due-title{ font-size:1.05rem; color:var(--ink); }
.srs-due-title b{ color:var(--brand); font-size:1.35rem; }
.srs-due-sub{ font-size:.78rem; color:var(--muted); margin-top:4px; }

.srs-card{
  background:var(--card); border:1px solid var(--line);
  border-radius:var(--radius); padding:38px 24px; text-align:center;
  margin:6px 0 10px;
}
.srs-word{
  font-size:2rem; font-weight:600; color:var(--ink); letter-spacing:-.01em;
  font-family:"Georgia", "Times New Roman", serif;
}
.srs-meta{ font-size:.76rem; color:var(--muted); margin-top:10px; }
.srs-ans{
  margin-top:18px; padding-top:18px; border-top:1px solid var(--line);
  font-size:.95rem; color:var(--ink); text-align:left;
}
.srs-ans .srs-meaning{ font-size:1.02rem; color:var(--brand); font-weight:500; }
.srs-ans .srs-example{
  font-size:.85rem; color:var(--muted); margin-top:8px; line-height:1.6;
  white-space:pre-wrap;
}
.srs-hint{
  text-align:center; font-size:.8rem; color:var(--muted); margin-top:10px;
}

/* ---- 条形图（错误画像用；不用 st.bar_chart 是因为中文字体在
       altair 默认主题下会掉字，而且配色跟本站主题对不上）---- */
.bars{ display:flex; flex-direction:column; gap:9px; margin:6px 0 4px; }
.bar-row{ display:flex; align-items:center; gap:12px; }
.bar-label{
  width:112px; flex:none; font-size:.82rem; color:var(--ink);
  text-align:right; line-height:1.3;
}
.bar-track{
  flex:1; height:18px; border-radius:5px; background:#F1EFE8;
  overflow:hidden;
}
.bar-fill{
  display:block;              /* 同上：inline span 上写 width 无效，条会整条消失 */
  height:100%; border-radius:5px; background:var(--brand);
  transition:width .4s ease;
}
.bar-fill.dim{ background:#B9CFC8; }
.bar-val{
  width:84px; flex:none; font-size:.78rem; color:var(--muted);  /* 64px 放不下"4 次 · 40.0%"，会折行 */
  text-align:right; white-space:nowrap;
  font-variant-numeric:tabular-nums;
}
</style>
"""


def inject_css():
    """在 set_page_config 之后、任何内容之前调用一次。"""
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def switch_view(view):
    """顶部卡片被点：切到对应界面。

    只改 session_state，不碰 URL、不整页重载——
    Streamlit 自己会 rerun，刚分析完的句子、刚生成的片段全都还在。
    """
    st.session_state["view"] = view


def hero(username, rank_name, pts, streak, done, total):
    """顶部状态条：把"今天该干什么"提到第一屏，并且四张卡都能点进去。

    · 段位 / 积分 / 连击 → 成长历程（段位阶梯、积分流水、打卡日历）
    · 今日任务           → 今日任务（四项清单、近七天记录、奖励规则）

    done/total 是今日任务完成数，放在最右边做进度提示。
    """
    u = html.escape(str(username))

    with st.container(border=True):
        # 这个空 div 只做锚点：CSS 靠 :has(.hero-anchor) 找到这块容器，
        # 从而在不碰 Streamlit 内部类名的前提下给它套上卡片外框。
        st.markdown('<div class="hero-anchor"></div>', unsafe_allow_html=True)

        left, right = st.columns([2, 3.6], gap="large", vertical_alignment="bottom")

        with left:
            st.markdown(
                f'<div class="hero-title">地道英语思维训练器</div>'
                f'<div class="hero-sub">你好，{u}　·　读一点，写一点，每天十分钟</div>',
                unsafe_allow_html=True,
            )

        with right:
            c1, c2, c3, c4 = st.columns(4, gap="small")
            # 每个卡片 = 一行小标签 + 一个按钮。
            # 按钮 label 里放不了两行，所以"段位""积分"这些名称走 caption。
            with c1:
                st.caption("段位")
                st.button(str(rank_name), key="hero_rank", width="stretch",
                          on_click=switch_view, args=("growth",),
                          help="看成长历程：段位阶梯 · 积分流水 · 打卡日历")
            with c2:
                st.caption("积分")
                st.button(f"{int(pts)}", key="hero_points", width="stretch",
                          on_click=switch_view, args=("growth",),
                          help="看积分都是从哪来的")
            with c3:
                st.caption("连击")
                st.button(f"{int(streak)} 天", key="hero_streak", width="stretch",
                          on_click=switch_view, args=("growth",),
                          help="看最近哪些天打过卡")
            with c4:
                st.caption("今日任务")
                st.button(f"{int(done)}/{int(total)}", key="hero_quests", width="stretch",
                          on_click=switch_view, args=("quests",),
                          help="看今天还差什么、能拿多少分")


def bar_chart(rows, max_rows=6):
    """错误画像的横向条形图。

    rows: [{"type": 名称, "count": 次数, "pct": 占比}, ...]（已按次数降序）
    只画前 max_rows 条；第一条用深色，其余淡色——一眼能看出"最严重的是哪个"。
    宽度按"占最大值的比例"算，不是按百分比，否则最大项也只剩半条，浪费空间。
    """
    if not rows:
        return

    rows = rows[:max_rows]
    top_count = max(r["count"] for r in rows) or 1
    parts = []
    for i, r in enumerate(rows):
        width = max(r["count"] / top_count * 100, 4)   # 最小 4%，太细的条看不见
        cls = "bar-fill" if i == 0 else "bar-fill dim"
        label = html.escape(str(r["type"]))
        parts.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{label}</div>'
            f'<div class="bar-track"><div class="{cls}" style="width:{width:.1f}%"></div></div>'
            f'<div class="bar-val">{r["count"]} 次 · {r["pct"]}%</div>'
            f"</div>"
        )

    st.markdown(f'<div class="bars">{"".join(parts)}</div>', unsafe_allow_html=True)
