"""操作计划总览：统计卡片 + 全部计划列表 + 编辑 / 删除。"""
from datetime import date, timedelta

import streamlit as st

from database.db import get_session
from services.akshare_service import is_trade_date
from services.plan_service import (
    delete_plan,
    get_plan,
    get_plan_stats,
    list_plans_by_user,
    update_plan,
)
from utils.page import render_page_header, render_sidebar_user

user = render_page_header("操作计划", "📋", "查看和管理所有操作计划")
render_sidebar_user()

# ============================================================
# 统计卡片
# ============================================================

with get_session() as session:
    total, completed, rate = get_plan_stats(session, user["id"])

stat_cols = st.columns(3)
stat_cols[0].metric("计划总数", total)
stat_cols[1].metric("已完成", completed)
stat_cols[2].metric("完成率", f"{rate}%")

st.divider()

# ============================================================
# 操作计划列表
# ============================================================

st.subheader("全部操作计划")

with get_session() as session:
    plans = list_plans_by_user(session, user["id"], limit=200)

if not plans:
    st.info("暂无操作计划。前往「股票分析」页面，对关注的股票添加操作计划。")
else:
    for p in plans:
        # 每行布局：状态 | 股票信息 | 日期 | 内容 | 操作按钮
        status_icon = "✅" if p.status == "completed" else "⏳"
        status_label = "已完成" if p.status == "completed" else "待完成"
        stock_label = f"{p.code} {p.name} · {p.market}"

        with st.container(border=True):
            row = st.columns([1, 2, 1, 2, 1, 1])
            with row[0]:
                st.markdown(f"**{status_icon}**")
            with row[1]:
                st.markdown(f"**{stock_label}**")
                st.caption(p.pool_name)
            with row[2]:
                st.write(p.plan_date.isoformat())
            with row[3]:
                st.write(p.content[:80] + ("..." if len(p.content) > 80 else ""))
            with row[4]:
                if p.status == "pending" and p.user_id == user["id"]:
                    if st.button("✏️ 编辑", key=f"plan_edit_{p.id}", use_container_width=True):
                        st.session_state["edit_plan_page_id"] = p.id
                        st.rerun()
            with row[5]:
                if p.user_id == user["id"]:
                    if st.button("🗑️ 删除", key=f"plan_del_{p.id}", use_container_width=True):
                        st.session_state["delete_plan_page_id"] = p.id
                        st.rerun()

# ============================================================
# 编辑弹窗
# ============================================================

edit_id = st.session_state.get("edit_plan_page_id")
if edit_id:
    st.session_state.pop("edit_plan_page_id", None)
    with get_session() as s:
        ep = get_plan(s, edit_id)
    if ep:
        @st.dialog("编辑操作计划", width="small")
        def _edit_page_plan():
            edit_date = st.date_input(
                "操作日期",
                value=ep.plan_date,
                min_value=date.today(),
                key="page_edit_plan_date",
            )
            edit_content = st.text_area(
                "计划内容",
                value=ep.content,
                key="page_edit_plan_content",
                height=120,
            )
            col_cancel, col_save = st.columns(2)
            with col_cancel:
                if st.button("取消", use_container_width=True):
                    for k in ("page_edit_plan_date", "page_edit_plan_content"):
                        st.session_state.pop(k, None)
                    st.rerun()
            with col_save:
                if st.button("保存", type="primary", use_container_width=True):
                    final_date = st.session_state.get("page_edit_plan_date") or ep.plan_date
                    final_content = (st.session_state.get("page_edit_plan_content") or "").strip()
                    if not final_content:
                        st.error("计划内容不能为空")
                    elif not is_trade_date(final_date.isoformat()):
                        st.error("所选日期非 A 股交易日，请重新选择")
                    else:
                        try:
                            with get_session() as s2:
                                update_plan(s2, ep.id, user["id"], final_date, final_content)
                            st.toast("已更新操作计划", icon="✅")
                            for k in ("page_edit_plan_date", "page_edit_plan_content"):
                                st.session_state.pop(k, None)
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                        except Exception:
                            st.error("操作失败，请稍后重试")

        _edit_page_plan()

# ============================================================
# 删除确认弹窗
# ============================================================

del_id = st.session_state.get("delete_plan_page_id")
if del_id:
    st.session_state.pop("delete_plan_page_id", None)
    with get_session() as s:
        dp = get_plan(s, del_id)
    if dp:
        @st.dialog("删除操作计划", width="small")
        def _delete_page_plan():
            st.warning(f"确认删除对 {dp.code} {dp.name} 的操作计划？")
            st.write(f"日期：{dp.plan_date.isoformat()}")
            st.write(f"内容：{dp.content[:100]}")

            col_cancel, col_conf = st.columns(2)
            with col_cancel:
                if st.button("取消", use_container_width=True):
                    st.rerun()
            with col_conf:
                if st.button("确认删除", type="primary", use_container_width=True):
                    try:
                        with get_session() as s2:
                            delete_plan(s2, dp.id, user["id"])
                        st.toast("已删除操作计划", icon="🗑️")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception:
                        st.error("操作失败，请稍后重试")

        _delete_page_plan()