"""系统初始化：首次部署时创建数据库表与管理员账号。"""
import streamlit as st

from auth.password import hash_password
from auth.session import login_user
from database.db import get_session
from database.init_db import init_db
from database.models import User

st.set_page_config(
    page_title="系统初始化 · TradeNote",
    page_icon="🔧",
    layout="centered",
)


def _is_initialized() -> bool:
    with get_session() as session:
        return session.query(User).filter_by(role="admin").first() is not None


def main() -> None:
    st.title("🔧 系统初始化")
    st.caption("首次部署 TradeNote 时，需要先创建数据库表和管理员账号。")

    init_db()

    if _is_initialized():
        st.success("✅ 系统已初始化完成，已有管理员账号。")
        if st.button("前往登录", type="primary", use_container_width=True):
            st.switch_page("pages/0_📊_仪表盘.py")
        return

    st.markdown("---")
    st.markdown("**创建首个管理员账号**")

    with st.form("init_form", clear_on_submit=False):
        username = st.text_input("管理员用户名", max_chars=64)
        password = st.text_input("管理员密码", type="password")
        password_confirm = st.text_input("确认密码", type="password")
        submitted = st.form_submit_button("创建并初始化", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not username or not username.strip():
            errors.append("用户名不能为空")
        if not password:
            errors.append("密码不能为空")
        elif len(password) < 6:
            errors.append("密码至少 6 位")
        if password != password_confirm:
            errors.append("两次密码输入不一致")
        if errors:
            for e in errors:
                st.error(e)
            return

        username = username.strip()

        with get_session() as session:
            if session.query(User).filter_by(username=username).first():
                st.error(f"用户名 {username} 已存在")
                return

            user = User(
                username=username,
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
                created_by=None,
            )
            session.add(user)
            session.flush()
            user_id = user.id
            user_username = user.username
            user_role = user.role

        login_user(user_id, user_username, user_role)
        st.toast(f"🎉 系统初始化完成！管理员账号：{username}", icon="✅")
        st.switch_page("pages/0_📊_仪表盘.py")


main()
