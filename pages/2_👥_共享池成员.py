"""池设置：成员管理（共享池）+ 飞书 Webhook。"""
import streamlit as st

from database.db import get_session
from services.pool_service import (
    add_member,
    can_access_pool,
    get_pool,
    get_pool_dto,
    is_pool_owner,
    list_candidate_users,
    list_pool_members,
    remove_member,
    set_feishu_webhook,
    validate_feishu_webhook,
)
from utils.date_util import format_date
from utils.page import render_back_to_pools_button, render_page_header, render_sidebar_user
from utils.ui import render_empty_state

user = render_page_header("共享股票池管理设置", "⚙️", "成员管理 · 飞书 Webhook 通知")
render_sidebar_user()

# ============================================================
# 读取页面参数
# ============================================================

pool_id_str = st.session_state.get("pool_id")
if not pool_id_str:
    st.info("📍 此页面需要从「我的股票池」进入。")
    render_back_to_pools_button()
    st.stop()

try:
    pool_id = int(pool_id_str)
except ValueError:
    st.error("无效的股票池 ID。")
    render_back_to_pools_button()
    st.stop()

# ============================================================
# 校验存在 & 访问权限
# ============================================================

with get_session() as session:
    pool = get_pool(session, pool_id)
    pool_dto = get_pool_dto(session, pool_id)
    if not pool or not pool_dto:
        st.error("股票池不存在或已被删除。")
        render_back_to_pools_button()
        st.stop()

    accessible = can_access_pool(session, pool_id, user["id"])
    if not accessible:
        st.error("你无权访问该股票池。")
        render_back_to_pools_button()
        st.stop()

    is_owner = is_pool_owner(session, pool_id, user["id"])
    is_creator = pool.creator_id == user["id"]
    feishu_webhook = pool.feishu_webhook

    if pool_dto.type == "shared":
        members = list_pool_members(session, pool_id)
        candidates = list_candidate_users(session, pool_id) if is_owner else []
    else:
        members = []
        candidates = []

# ============================================================
# 顶部信息
# ============================================================

st.subheader(f"当前股票池： {pool_dto.name}")
st.caption(
    f"类型：{'👥 共享池' if pool_dto.type == 'shared' else '🔒 私有池'} · "
    f"创建者：{pool_dto.creator_username} · 创建于 {format_date(pool_dto.created_at)}"
)

col_back, _ = st.columns([1, 5])
with col_back:
    render_back_to_pools_button()

st.divider()

# ============================================================
# 成员管理（仅共享池）
# ============================================================

if pool_dto.type == "shared":
    st.subheader(f"👥 成员管理（{len(members)}）")

    if not members:
        render_empty_state("暂无成员", icon="👥")
    else:
        cols = st.columns([3, 2, 3, 2])
        cols[0].markdown("**用户名**")
        cols[1].markdown("**角色**")
        cols[2].markdown("**加入时间**")
        cols[3].markdown("**操作**")
        st.divider()

        for m in members:
            cols = st.columns([3, 2, 3, 2])
            cols[0].write(m.username + (" (你)" if m.user_id == user["id"] else ""))
            cols[1].write("👑 Owner" if m.role == "owner" else "Member")
            cols[2].write(format_date(m.added_at))
            with cols[3]:
                if m.role == "owner":
                    cols[3].caption("不可移除")
                elif is_owner:
                    if st.button("移除", key=f"rm_{m.id}"):
                        try:
                            with get_session() as s:
                                remove_member(s, pool_id, m.user_id)
                            st.toast(f"已移除成员 {m.username}", icon="✅")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                        except Exception:
                            st.error("操作失败，请稍后重试")
                else:
                    cols[3].caption("—")

    st.divider()

    # 邀请新成员（仅 owner）
    if not is_owner:
        st.info("仅 Owner 可邀请新成员。")
    else:
        st.subheader("邀请新成员")

        if not candidates:
            render_empty_state("所有启用的用户均已加入该池，无可邀请的人选", icon="✅")
        else:
            with st.form("invite_member_form", clear_on_submit=True):
                options = {u.id: f"{u.username}" for u in candidates}
                selected_id = st.selectbox(
                    "选择用户",
                    options=list(options.keys()),
                    format_func=lambda uid: options[uid],
                    key="invite_user_select",
                )
                if st.form_submit_button("添加成员", type="primary"):
                    try:
                        with get_session() as s:
                            add_member(s, pool_id, selected_id)
                        st.toast(f"已添加成员 {options[selected_id]}", icon="✅")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception:
                        st.error("操作失败，请稍后重试")

    st.divider()

# ============================================================
# 飞书 Webhook
# ============================================================

st.subheader("🤖 飞书机器人 Webhook")

current_webhook = feishu_webhook

if is_creator:
    with st.form("webhook_form"):
        webhook_url = st.text_input(
            "Webhook 地址",
            value=current_webhook or "",
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/...",
            help="填写飞书机器人 Webhook 地址，留空则清空",
        )
        if st.form_submit_button("保存", type="primary"):
            url = (webhook_url or "").strip()
            try:
                with get_session() as s:
                    set_feishu_webhook(s, pool_id, user["id"], url or None)
                if url:
                    st.toast("已保存 Webhook 设置", icon="✅")
                else:
                    st.toast("已清空 Webhook 设置", icon="✅")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
else:
    if current_webhook:
        st.markdown("✅ 已设置（仅池主可修改）")
        st.code(current_webhook, language="text")
    else:
        st.markdown("❌ 未设置")
