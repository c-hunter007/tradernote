"""复盘归档：查看所有已移出股票池的股票。"""
import html

import streamlit as st

from database.db import get_session
from services.pool_service import list_my_pools
from services.stock_service import (
    list_all_removed_stocks_for_user,
    list_removed_pool_stocks,
)
from utils.date_util import format_date
from utils.page import render_page_header, render_sidebar_user
from utils.ui import COLOR_MUTED, render_empty_state, render_removed_card

user = render_page_header("复盘归档", "♻️", "查看所有已移出股票池的股票")
render_sidebar_user()

# ============================================================
# 顶部：池筛选下拉框
# ============================================================

with get_session() as session:
    my_pools = list_my_pools(session, user["id"])

# 构建下拉选项：全部池 + 用户可见的池
# 用 id 作为索引，-1 表示「全部池」
pool_options = {-1: "全部池"}
for p in my_pools:
    pool_options[p.id] = p.name

col_filter, _ = st.columns([2, 4])
with col_filter:
    selected_pool_id = st.selectbox(
        "筛选池",
        options=list(pool_options.keys()),
        format_func=lambda x: pool_options[x],
        key="removed_filter_pool",
    )

st.divider()

# ============================================================
# 已移出股票列表
# ============================================================

with get_session() as session:
    if selected_pool_id == -1:
        removed_stocks = list_all_removed_stocks_for_user(session, user["id"])
    else:
        removed_stocks = list_removed_pool_stocks(session, selected_pool_id)

if not removed_stocks:
    render_empty_state("暂无已移出的股票", icon="♻️")
else:
    st.caption(f"共 {len(removed_stocks)} 条已移出记录（按移出时间倒序）")
    for s in removed_stocks:
        # 卡片标题
        title = f"{s.code} {s.name} · {s.market}"

        # 卡片正文（用户内容需转义）
        body_parts = []
        if s.pool_name:
            body_parts.append(f"所属池：{html.escape(s.pool_name)}")
        body_parts.append(f"加入者：{html.escape(s.added_by_username)}")
        body_parts.append(f"加入于 {format_date(s.added_date)}")
        if s.removed_by_username:
            body_parts.append(f"移出者：{html.escape(s.removed_by_username)}")
        if s.removed_date:
            body_parts.append(f"移出于 {format_date(s.removed_date)}")
        body_parts.append(f"分析结论：{s.note_count} 条")
        body = " · ".join(body_parts)

        if s.removal_analysis:
            body += (
                f"<br/><span style='color:{COLOR_MUTED};'>"
                f"移出原因：{html.escape(s.removal_analysis)}</span>"
            )

        render_removed_card(title=title, body=body)

        # 操作按钮
        col_view, _ = st.columns([1, 5])
        with col_view:
            if st.button("📝 查看分析历史", key=f"view_{s.id}", use_container_width=True):
                st.session_state["pool_stock_id"] = s.id
                st.switch_page(st.session_state["_hidden_analysis_page"])
        st.write("")
