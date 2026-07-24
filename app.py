"""TradeNote 应用入口：多页导航路由。"""
import streamlit as st

from auth.session import flush_pending_cookies, init_cookies, is_admin, restore_from_cookie
from database.init_db import init_db
from config import VERSION

init_db()
init_cookies()
flush_pending_cookies()
restore_from_cookie()

# ── 定义页面 ──
dashboard = st.Page("pages/0_📊_仪表盘.py", title="仪表盘", icon="📊")
pool = st.Page("pages/1_📈_我的股票池.py", title="我的股票池", icon="📈")
members = st.Page("pages/2_👥_共享池成员.py", title="股票池设置", icon="⚙️", visibility="hidden")
pool_detail = st.Page("pages/3_🔍_股票池详情.py", title="股票池详情", icon="🔍")
analysis = st.Page("pages/4_📝_股票分析.py", title="股票分析", icon="📝", visibility="hidden")
review = st.Page("pages/5_♻️_复盘归档.py", title="复盘归档", icon="♻️")
trading = st.Page("pages/9_🚧_交易记录.py", title="交易记录", icon="🚧")
admin_page = st.Page("pages/0_🛡️_管理后台.py", title="管理后台", icon="🛡️")
init_page = st.Page("pages/0_🔧_系统初始化.py", title="系统初始化", icon="🔧", visibility="hidden")

# ── 保存引用供各页面 switch_page 使用 ──
st.session_state["_page_dashboard"] = dashboard
st.session_state["_page_pool"] = pool
st.session_state["_page_members"] = members
st.session_state["_page_pool_detail"] = pool_detail
st.session_state["_hidden_analysis_page"] = analysis
st.session_state["_page_review"] = review
st.session_state["_page_trading"] = trading
st.session_state["_page_admin"] = admin_page
st.session_state["_page_init"] = init_page

# ── 可见页面列表（侧边栏导航用） ──
visible_pages = [dashboard, pool, members, review, trading]
if is_admin():
    visible_pages.append(admin_page)

# ── 所有页面列表（路由用，含隐藏页） ──
all_pages = [dashboard, pool, members, pool_detail, review, trading, analysis, init_page]
if is_admin():
    all_pages.append(admin_page)

# ── 侧边栏 ──
with st.sidebar:
    st.markdown("### 📊 TraderNote")
    st.caption(f"多人股票跟踪记录工具 · v{VERSION}")
    st.divider()
    for p in visible_pages:
        st.page_link(p)
    st.divider()

# ── 导航 ──
pg = st.navigation(all_pages, position="hidden")
pg.run()
