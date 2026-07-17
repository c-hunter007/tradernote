"""管理后台：账号管理（仅管理员可访问）。"""
import streamlit as st

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
