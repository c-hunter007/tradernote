"""管理后台：账号管理（仅管理员可访问）。"""
import streamlit as st

from config import DB_PATH
from database.db import get_session
from services.user_service import (
    count_admins,
    create_user,
    list_users,
    reset_password,
    set_role,
    toggle_active,
)
from utils.page import render_admin_page_header, render_sidebar_user
from utils.ui import render_empty_state

user = render_admin_page_header("管理后台", "🛡️")
st.caption(f"当前管理员：{user['username']}")
render_sidebar_user()

# ========== 用户列表 ==========
st.subheader("用户列表")

with get_session() as session:
    users = list_users(session)

if not users:
    render_empty_state("暂无用户", icon="👤")
else:
    cols = st.columns([3, 4, 2, 2, 2])
    cols[0].markdown("**用户名**")
    cols[1].markdown("**创建者**")
    cols[2].markdown("**角色**")
    cols[3].markdown("**状态**")
    cols[4].markdown("**操作**")
    st.divider()

    for u in users:
        cols = st.columns([3, 4, 2, 2, 2])
        cols[0].write(u.username + (" (你)" if u.id == user["id"] else ""))
        cols[1].write(u.created_by_username or "（初始管理员）")
        cols[2].write("管理员" if u.role == "admin" else "普通用户")
        cols[3].write("启用" if u.is_active else "禁用")
        with cols[4]:
            col_a, col_b, col_c = st.columns(3)
            # 重置密码
            if col_a.button("改密", key=f"reset_{u.id}", help="重置密码"):
                st.session_state[f"reset_open_{u.id}"] = True
                st.rerun()
            # 启用/禁用（可逆，无二次确认）
            label = "禁用" if u.is_active else "启用"
            if col_b.button(label, key=f"toggle_{u.id}"):
                try:
                    with get_session() as s2:
                        if u.is_active and u.role == "admin":
                            admin_cnt = count_admins(s2)
                            if admin_cnt <= 1:
                                st.error("无法禁用最后一个管理员账号。")
                                st.stop()
                        new_state = toggle_active(s2, u.id)
                    st.toast(f"已{'启用' if new_state else '禁用'} {u.username}", icon="✅")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception:
                    st.error("操作失败，请稍后重试")
            # 角色：升降级。降级管理员是较重操作 → 二次确认
            role_btn_label = "降级" if u.role == "admin" else "升级"
            if col_c.button(role_btn_label, key=f"role_{u.id}"):
                st.session_state[f"confirm_role_{u.id}"] = True
                st.rerun()

        # 降级管理员二次确认框
        if st.session_state.get(f"confirm_role_{u.id}"):
            new_role = "user" if u.role == "admin" else "admin"
            with st.container(border=True):
                st.warning(f"确认将 **{u.username}** 设为{'普通用户' if new_role == 'user' else '管理员'}？")
                cc1, cc2, _ = st.columns([1, 1, 3])
                if cc1.button("确认", key=f"role_confirm_{u.id}", type="primary"):
                    try:
                        with get_session() as s3:
                            if u.role == "admin" and count_admins(s3) <= 1:
                                st.error("无法降级最后一个管理员账号。")
                                st.stop()
                            if u.id == user["id"] and new_role == "user":
                                st.error("不能降级自己，请先由其他管理员操作。")
                                st.stop()
                            set_role(s3, u.id, new_role)
                        st.toast(
                            f"已将 {u.username} 设置为{'管理员' if new_role == 'admin' else '普通用户'}",
                            icon="✅",
                        )
                        st.session_state.pop(f"confirm_role_{u.id}", None)
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception:
                        st.error("操作失败，请稍后重试")
                if cc2.button("取消", key=f"role_cancel_{u.id}"):
                    st.session_state.pop(f"confirm_role_{u.id}", None)
                    st.rerun()

        # 改密面板（展开式）
        if st.session_state.get(f"reset_open_{u.id}"):
            with st.container(border=True):
                st.write(f"重置 **{u.username}** 的密码")
                new_pwd = st.text_input(
                    "新密码",
                    type="password",
                    key=f"new_pwd_{u.id}",
                    help="至少 6 位",
                )
                confirm_pwd = st.text_input(
                    "确认新密码",
                    type="password",
                    key=f"confirm_pwd_{u.id}",
                )
                cc1, cc2 = st.columns([1, 4])
                if cc1.button("确认", key=f"confirm_btn_{u.id}", type="primary"):
                    if len(new_pwd) < 6:
                        st.error("密码至少 6 位。")
                    elif new_pwd != confirm_pwd:
                        st.error("两次输入不一致。")
                    else:
                        try:
                            with get_session() as s4:
                                reset_password(s4, u.id, new_pwd)
                            st.toast(f"已重置 {u.username} 的密码", icon="✅")
                            st.session_state.pop(f"reset_open_{u.id}", None)
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                        except Exception:
                            st.error("操作失败，请稍后重试")
                if cc2.button("取消", key=f"cancel_btn_{u.id}"):
                    st.session_state.pop(f"reset_open_{u.id}", None)
                    st.rerun()

st.divider()

# ========== 创建账号 ==========
st.subheader("创建新账号")

with st.form("create_user_form", clear_on_submit=True):
    new_username = st.text_input("用户名", max_chars=64, key="new_username")
    new_password = st.text_input("密码", type="password", help="至少 6 位", key="new_password")
    confirm_password = st.text_input("确认密码", type="password", key="confirm_password")
    new_role = st.selectbox(
        "角色",
        options=["user", "admin"],
        format_func=lambda x: "普通用户" if x == "user" else "管理员",
        key="new_role",
    )
    submitted = st.form_submit_button("创建账号", type="primary")

    if submitted:
        if not new_username or not new_password:
            st.error("用户名和密码不能为空。")
        elif len(new_password) < 6:
            st.error("密码至少 6 位。")
        elif new_password != confirm_password:
            st.error("两次密码不一致。")
        else:
            try:
                with get_session() as session:
                    create_user(
                        session,
                        username=new_username,
                        password=new_password,
                        role=new_role,
                        creator_id=user["id"],
                    )
                st.toast(f"已创建账号 {new_username}", icon="✅")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error("操作失败，请稍后重试")

st.divider()
st.subheader("📦 数据库管理")

# ── 备份 ──
with st.container(border=True):
    st.markdown("**📥 备份数据库**")
    st.caption("下载当前数据库文件，包含所有用户、股票池、分析记录、交易记录等数据。")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 生成备份"):
            from sqlalchemy import text
            from database.db import engine
            with engine.connect() as conn:
                conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            st.session_state["backup_ready"] = True
            st.rerun()
    with col2:
        if st.session_state.get("backup_ready"):
            from datetime import datetime
            db_bytes = DB_PATH.read_bytes()
            st.download_button(
                "📥 下载备份文件",
                data=db_bytes,
                file_name=f"tradernote_{datetime.now():%Y%m%d_%H%M%S}.db",
                mime="application/octet-stream",
                on_click=lambda: st.session_state.pop("backup_ready", None),
            )

# ── 导入 ──
with st.container(border=True):
    st.markdown("**📤 导入数据库**")
    st.caption("上传 .db 备份文件覆盖当前数据库。所有现有数据将被替换。")

    uploaded = st.file_uploader("选择备份文件", type=["db"], key="db_import")
    if uploaded is not None:
        uploaded_bytes = uploaded.getvalue()

        import sqlite3, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(uploaded_bytes)
            tmp_path = tmp.name
        try:
            conn = sqlite3.connect(tmp_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            if cursor.fetchone() is None:
                st.error("无效的数据库文件：缺少 users 表")
                st.stop()
            conn.close()
        except Exception:
            st.error("无效的数据库文件，无法打开")
            st.stop()
        finally:
            os.unlink(tmp_path)

        st.warning("⚠️ 导入将覆盖所有现有数据，此操作不可恢复。导入后你将需要重新登录。")
        if st.button("确认导入", type="primary"):
            try:
                from database.db import engine
                engine.dispose()
                DB_PATH.write_bytes(uploaded_bytes)
                for suffix in ("-wal", "-shm"):
                    extra = DB_PATH.with_name(DB_PATH.name + suffix)
                    if extra.exists():
                        extra.unlink()
                from database.init_db import init_db
                init_db()
                from auth.session import logout_user
                logout_user()
                st.toast("数据库已导入，请重新登录", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"导入失败：{e}")
