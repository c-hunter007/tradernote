"""页面通用辅助：登录校验、页面头部装饰等。"""
import streamlit as st

from auth.session import current_user, init_cookies, require_admin, require_login


def render_page_header(title: str, icon: str, caption: str | None = None) -> dict:
    """渲染页面统一头部，返回当前用户 dict。"""
    st.set_page_config(
        page_title=f"{title} · TradeNote",
        page_icon=icon,
        layout="wide",
    )
    user = require_login()
    st.title(f"{icon} {title}")
    if caption:
        st.caption(caption)
    return user


def render_admin_page_header(title: str, icon: str) -> dict:
    """渲染管理员页面统一头部，返回当前用户 dict。非管理员会被拦截。"""
    st.set_page_config(
        page_title=f"{title} · TradeNote",
        page_icon=icon,
        layout="wide",
    )
    user = require_admin()
    st.title(f"{icon} {title}")
    return user


def render_sidebar_user() -> None:
    """在侧边栏展示当前用户与退出按钮（每个页面统一调用）。"""
    with st.sidebar:
        user = current_user()
        if user:
            st.write(f"👤 **{user['username']}**")
            if user["role"] == "admin":
                st.caption("管理员")
            if st.button("退出登录", use_container_width=True, key="sidebar_logout"):
                from auth.session import logout_user
                logout_user()
                st.toast("已退出登录", icon="👋")
                st.rerun()
        st.write("")
        st.write("")
        st.caption("Powered by Streamlit")


def render_back_to_pools_button(label: str = "← 返回我的股票池", primary: bool = False) -> None:
    """渲染"返回我的股票池"按钮，点击后跳转到「我的股票池」页。

    Args:
        label: 按钮文案，默认统一为"← 返回我的股票池"。
        primary: 是否使用 primary 样式，默认 False（次级灰色按钮）。
    """
    if st.button(label, type="primary" if primary else "secondary"):
        st.switch_page(st.session_state["_page_pool"])
