"""TradeNote 仪表盘：登录页 + 仪表盘概览。"""
import streamlit as st

st.set_page_config(
    page_title="TradeNote · 股票跟踪",
    page_icon="📊",
    layout="wide",
)

from auth.password import verify_password
from auth.session import (
    current_user,
    is_logged_in,
    login_user,
)
from database.db import get_session
from database.models import User
from services.activity_service import list_recent_activities
from services.pool_service import list_my_pools
from services.stock_service import (
    count_active_stocks_for_user,
    count_key_focus_stocks_for_user,
    count_total_notes_for_user,
)
from utils.date_util import format_datetime
from utils.page import render_sidebar_user
from utils.ui import render_empty_state


def render_login_page() -> None:
    st.title("📊 TradeNote")
    st.caption("股票跟踪记录 · 个人与小型团队工具")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("用户名", max_chars=64)
        password = st.text_input("密码", type="password")
        remember = st.checkbox("记住我（30 天）", value=True)
        submitted = st.form_submit_button("登录", type="primary", use_container_width=True)

    if submitted:
        if not username or not password:
            st.error("请输入用户名和密码。")
            return
        with get_session() as session:
            user = session.query(User).filter_by(username=username.strip()).first()
            if not user:
                st.error("用户名或密码错误。")
                return
            if not user.is_active:
                st.error("该账号已被禁用，请联系管理员。")
                return
            if not verify_password(password, user.password_hash):
                st.error("用户名或密码错误。")
                return
            login_user(user.id, user.username, user.role, remember=remember)
            st.toast(f"欢迎回来，{user.username}！", icon="✅")
            st.rerun()

    with get_session() as session:
        has_admin = session.query(User).filter_by(role="admin").first() is not None
    if not has_admin:
        st.markdown("---")
        st.warning("⚠️ 系统尚未初始化，请先创建管理员账号。")
        if st.button("🔧 初始化系统", type="primary", use_container_width=True):
            st.switch_page(st.session_state["_page_init"])


def _render_stat_card(icon: str, label: str, value: int) -> None:
    st.markdown(
        f"""
        <div style="background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px;
                    padding: 16px 12px; text-align: center;">
            <div style="font-size: 24px;">{icon}</div>
            <div style="font-size: 28px; font-weight: 700; color: #111827; margin: 4px 0;">{value}</div>
            <div style="font-size: 13px; color: #6b7280;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard(user: dict) -> None:
    st.title(f"欢迎，{user['username']}！")
    st.divider()

    with get_session() as session:
        pool_count = len(list_my_pools(session, user["id"]))
        active_stocks = count_active_stocks_for_user(session, user["id"])
        key_focus = count_key_focus_stocks_for_user(session, user["id"])
        total_notes = count_total_notes_for_user(session, user["id"])
        recent_activities = list_recent_activities(session, user["id"], limit=5)

    st.subheader("📈 统计概览")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _render_stat_card("📋", "股票池", pool_count)
    with c2:
        _render_stat_card("📊", "在池股票", active_stocks)
    with c3:
        _render_stat_card("⭐", "重点关注", key_focus)
    with c4:
        _render_stat_card("📝", "分析结论", total_notes)

    st.divider()

    st.subheader("🕒 近期活动")
    if not recent_activities:
        render_empty_state("暂无近期活动，前往「我的股票池」开始记录", icon="🕒")
    else:
        for a in recent_activities:
            with st.container(border=True):
                st.markdown(f"**{a.username}** · {format_datetime(a.created_at)} · {a.description}")

    st.divider()

    st.subheader("🔗 快速入口")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.page_link("pages/1_📈_我的股票池.py", label="前往「我的股票池」", icon="📈", width="stretch")
    with col2:
        st.page_link("pages/5_♻️_复盘归档.py", label="前往「复盘归档」", icon="♻️", width="stretch")
    with col3:
        if user["role"] == "admin":
            st.page_link("pages/0_🛡️_管理后台.py", label="前往「管理后台」", icon="🛡️", width="stretch")


def main() -> None:
    render_sidebar_user()

    if is_logged_in():
        render_dashboard(current_user())
    else:
        render_login_page()


main()
