"""我的股票池：池列表 + 新建池 + 删除池 + 入口按钮。"""
import streamlit as st

from database.db import get_session
from services.pool_service import (
    check_duplicate_name,
    create_pool,
    delete_pool,
    list_my_pools,
)
from utils.date_util import format_date
from utils.page import render_page_header, render_sidebar_user
from utils.ui import render_card, render_empty_state

user = render_page_header("我的股票池", "📈", "管理你的私有 / 共享股票池")
render_sidebar_user()

# ============================================================
# 新建股票池（弹出对话框）
# ============================================================

@st.dialog("新建股票池", width="small")
def _create_pool_dialog():
    name = st.text_input("股票池名称", max_chars=128, key="new_pool_name")
    pool_type = st.radio(
        "类型",
        options=["private", "shared"],
        format_func=lambda x: "🔒 私有池（仅自己可见）" if x == "private" else "👥 共享池（可邀请成员协作）",
        key="new_pool_type",
        horizontal=True,
    )

    # 同名池软提示（仅提示，不阻止）
    name_stripped = (name or "").strip()
    if name_stripped:
        with get_session() as session:
            has_dup = check_duplicate_name(session, user["id"], name_stripped)
        if has_dup:
            st.warning("⚠️ 你已存在同名股票池，是否仍要继续创建？")

    if st.button("创建", type="primary", use_container_width=True, disabled=not name_stripped):
        try:
            with get_session() as session:
                create_pool(
                    session,
                    name=name_stripped,
                    pool_type=pool_type,
                    creator_id=user["id"],
                )
            st.toast(f"已创建股票池「{name_stripped}」", icon="✅")
            st.rerun()
        except ValueError as e:
            st.error(str(e))


# ============================================================
# 顶部操作栏
# ============================================================

col_title, col_btn = st.columns([5, 1])
with col_btn:
    if st.button("➕ 新建股票池", type="primary", use_container_width=True):
        _create_pool_dialog()

# ============================================================
# 列表（按类型过滤）
# ============================================================

with get_session() as session:
    pools = list_my_pools(session, user["id"])

tab_all, tab_private, tab_shared = st.tabs([
    f"全部（{len(pools)}）",
    f"私有（{sum(1 for p in pools if p.type == 'private')}）",
    f"共享（{sum(1 for p in pools if p.type == 'shared')}）",
])


def _filter_pools(items: list, type_filter: str | None) -> list:
    if type_filter is None:
        return items
    return [p for p in items if p.type == type_filter]


def _render_pool_card(p, key_prefix: str = "") -> None:
    """渲染单个股票池卡片。

    key_prefix 用于在多个 tab 中渲染同一池时避免 widget key 重复。
    """
    is_shared = p.type == "shared"
    type_label = "👥 共享池" if is_shared else "🔒 私有池"
    is_owner = p.creator_id == user["id"]

    # 卡片头部
    meta_parts = [type_label, f"创建者：{p.creator_username}", f"创建于 {format_date(p.created_at)}"]
    if is_shared:
        meta_parts.append(f"成员：{p.member_count}")
    meta_parts.append(f"在池股票：{p.active_stock_count}")

    body = " · ".join(meta_parts)
    title = f"{'👑 ' if is_owner else ''}{p.name}"
    render_card(title=title, body=body)

    # 操作按钮
    cols = st.columns([1, 1, 1, 3])
    with cols[0]:
        if st.button("进入详情", key=f"{key_prefix}enter_{p.id}", use_container_width=True):
            st.session_state["pool_id"] = p.id
            st.switch_page(st.session_state["_page_pool_detail"])
    with cols[1]:
        if is_shared:
            if st.button("设置管理", key=f"{key_prefix}member_{p.id}", use_container_width=True):
                st.session_state["pool_id"] = p.id
                st.switch_page(st.session_state["_page_members"])
        else:
            st.write("")  # 占位
    with cols[2]:
        if is_owner:
            if st.button("🗑️ 删除", key=f"{key_prefix}del_{p.id}", use_container_width=True):
                st.session_state[f"{key_prefix}confirm_delete_{p.id}"] = True
                st.rerun()
    st.divider()


def _render_delete_confirm(p, key_prefix: str = "") -> None:
    """渲染删除二次确认框。"""
    with st.container(border=True):
        st.warning(f"⚠️ 确认删除股票池「{p.name}」？")
        st.caption("将级联删除池内所有股票、分析结论、配图，操作不可恢复。")
        cc1, cc2, _ = st.columns([1, 1, 3])
        if cc1.button("确认删除", key=f"{key_prefix}confirm_{p.id}", type="primary"):
            try:
                with get_session() as session:
                    delete_pool(session, p.id)
                st.toast(f"已删除股票池「{p.name}」", icon="🗑️")
                st.session_state.pop(f"{key_prefix}confirm_delete_{p.id}", None)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error("操作失败，请稍后重试")
        if cc2.button("取消", key=f"{key_prefix}cancel_{p.id}"):
            st.session_state.pop(f"{key_prefix}confirm_delete_{p.id}", None)
            st.rerun()


def _render_pool_list(items: list, key_prefix: str = "") -> None:
    if not items:
        render_empty_state("暂无股票池，点击右上角「新建股票池」开始", icon="📈")
        return
    for p in items:
        _render_pool_card(p, key_prefix=key_prefix)
        if st.session_state.get(f"{key_prefix}confirm_delete_{p.id}"):
            _render_delete_confirm(p, key_prefix=key_prefix)


with tab_all:
    _render_pool_list(_filter_pools(pools, None), key_prefix="all_")

with tab_private:
    _render_pool_list(_filter_pools(pools, "private"), key_prefix="private_")

with tab_shared:
    _render_pool_list(_filter_pools(pools, "shared"), key_prefix="shared_")
