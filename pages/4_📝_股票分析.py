"""股票分析：单只股票分析历史 + 新增结论/配图 + 编辑/删除本人结论。"""
import os

import streamlit as st

from config import UPLOAD_DIR
from database.db import get_session
from services.analysis_service import (
    add_comment,
    create_note,
    delete_comment,
    delete_note,
    list_comments,
    list_note_images,
    list_notes,
    update_note,
    validate_image_file,
)
from services.pool_service import can_access_pool, get_pool_dto
from services.stock_service import get_pool_stock_dto
from utils.date_util import format_date, format_datetime
from utils.page import render_back_to_pools_button, render_page_header, render_sidebar_user
from utils.ui import render_empty_state

user = render_page_header("股票分析", "📝", "添加分析结论、上传配图")
render_sidebar_user()

# ============================================================
# 读取页面参数（从 session_state）
# ============================================================

pool_stock_id_str = st.session_state.get("pool_stock_id")
if not pool_stock_id_str:
    st.info("📍 此页面需要从「股票池详情」进入。\n\n请先前往「我的股票池」选择一个股票池，进入详情后点击「查看分析」。")
    render_back_to_pools_button()
    st.stop()

try:
    pool_stock_id = int(pool_stock_id_str)
except ValueError:
    st.error("无效的分析记录 ID。")
    render_back_to_pools_button()
    st.stop()

# ============================================================
# 校验 PoolStock 存在 & 访问权限
# ============================================================

with get_session() as session:
    ps_dto = get_pool_stock_dto(session, pool_stock_id)
    if not ps_dto:
        st.error("股票池中的股票不存在或已被删除。")
        render_back_to_pools_button()
        st.stop()

    pool_id = ps_dto.pool_id
    if not can_access_pool(session, pool_id, user["id"]):
        st.error("你无权访问该股票池。")
        render_back_to_pools_button()
        st.stop()

    pool_dto = get_pool_dto(session, pool_id)

# ============================================================
# 顶部信息
# ============================================================

st.subheader(f"{ps_dto.code} {ps_dto.name} · {ps_dto.market}")
caption_parts = [
    f"所属池：{pool_dto.name}",
    f"加入者：{ps_dto.added_by_username}",
    f"加入于 {format_date(ps_dto.added_date)}",
    f"分析结论：{ps_dto.note_count} 条",
]
if ps_dto.status == "removed":
    removed_at = format_date(ps_dto.removed_date) if ps_dto.removed_date else ""
    removed_by = ps_dto.removed_by_username or "?"
    caption_parts.append(f"⚠️ 已移出于 {removed_at}（移出人：{removed_by}）")
st.caption(" · ".join(caption_parts))
if ps_dto.initial_analysis:
    with st.container(border=True):
        st.markdown("**初始分析**")
        st.write(ps_dto.initial_analysis)
if ps_dto.status == "removed" and ps_dto.removal_analysis:
    with st.container(border=True):
        st.markdown("**移出原因**")
        st.write(ps_dto.removal_analysis)

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("← 返回池详情"):
        st.session_state["pool_id"] = pool_id
        st.switch_page(st.session_state["_page_pool_detail"])

st.divider()

# ============================================================
# 分析结论历史
# ============================================================

st.subheader("历史分析记录")

with get_session() as session:
    notes = list_notes(session, pool_stock_id)

if not notes:
    render_empty_state("暂无分析记录，使用下方表单添加第一条记录", icon="📝")
else:
    for n in notes:
        # 操作按钮（仅本人可见，放在卡片上方与卡片视觉关联）
        header_cols = st.columns([5, 1, 1])
        with header_cols[1]:
            if n.user_id == user["id"]:
                if st.button("✏️ 编辑", key=f"edit_btn_{n.id}", use_container_width=True):
                    st.session_state[f"edit_{n.id}"] = True
                    st.rerun()
        with header_cols[2]:
            if n.user_id == user["id"]:
                if st.button("🗑️ 删除", key=f"del_btn_{n.id}", use_container_width=True):
                    st.session_state[f"delete_{n.id}"] = True
                    st.rerun()

        # 卡片本体（含文字与配图）
        with st.container(border=True):
            meta_parts = [f"**{n.username}** · {format_datetime(n.created_at)}"]
            if n.image_paths:
                meta_parts.append(f"🖼 {len(n.image_paths)} 张配图")
            st.markdown(" · ".join(meta_parts))
            st.markdown(n.content)

            if n.image_paths:
                for rel_path in n.image_paths:
                    abs_path = str(UPLOAD_DIR / rel_path)
                    if os.path.exists(abs_path):
                        try:
                            st.image(abs_path, use_container_width=True)
                        except Exception:
                            st.warning(f"图片加载失败：{rel_path}")
                    else:
                        st.caption(f"文件缺失：{rel_path}")

        # ====== 点评区域 ======
        with st.expander(f"💬 点评 ({n.comment_count})", key=f"comments_{n.id}"):
            with get_session() as s:
                comments = list_comments(s, n.id)

            for i, c in enumerate(comments):
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(f"**{c.username}** · {format_datetime(c.created_at)}")
                    st.write(c.content)
                with c2:
                    if c.user_id == user["id"]:
                        if st.button("🗑️", key=f"del_comment_{c.id}", help="删除"):
                            with get_session() as s:
                                delete_comment(s, c.id, user["id"])
                            st.rerun()
                if i < len(comments) - 1:
                    st.divider()

            if prompt := st.chat_input("写点评...", key=f"chat_{n.id}"):
                with get_session() as s:
                    add_comment(s, n.id, user["id"], prompt)
                st.rerun()

        # ====== 编辑模式 ======
        if st.session_state.get(f"edit_{n.id}"):
            with st.container(border=True):
                st.markdown("**编辑分析结论**")
                edit_content = st.text_area(
                    "内容",
                    value=n.content,
                    key=f"edit_content_{n.id}",
                    height=120,
                )

                # 显示已有图片（可勾选移除）
                st.markdown("**当前配图**")
                with get_session() as session2:
                    existing_imgs = list_note_images(session2, n.id)
                removed_ids: list[int] = []
                if existing_imgs:
                    for img in existing_imgs:
                        abs_path = str(UPLOAD_DIR / img.file_path)
                        check_col, img_col = st.columns([1, 4])
                        with check_col:
                            if st.checkbox(
                                f"移除 #{img.id}",
                                value=False,
                                key=f"remove_img_{n.id}_{img.id}",
                            ):
                                removed_ids.append(img.id)
                        with img_col:
                            if os.path.exists(abs_path):
                                try:
                                    st.image(abs_path, width=200)
                                except Exception:
                                    st.caption("图片加载失败")
                            else:
                                st.caption(f"文件缺失：{img.id}")
                else:
                    st.caption("（无配图）")

                # 新增图片
                st.markdown("**新增配图**")
                new_files = st.file_uploader(
                    "选择新图片（最多 5 张）",
                    type=["png", "jpg", "jpeg", "gif", "webp"],
                    accept_multiple_files=True,
                    key=f"new_files_{n.id}",
                )
                if new_files:
                    if len(new_files) > 5:
                        st.error(f"单次最多上传 5 张图片，已选择 {len(new_files)} 张")
                    else:
                        for f in new_files:
                            ok, msg = validate_image_file(f)
                            if ok:
                                st.caption(f"✅ {f.name} ({f.size / 1024 / 1024:.2f}MB)")
                            else:
                                st.error(f"{f.name}：{msg}")

                # 保存/取消按钮
                save_cols = st.columns([1, 1, 3])
                if save_cols[0].button("保存", key=f"save_{n.id}", type="primary"):
                    new_content = (st.session_state.get(f"edit_content_{n.id}") or "").strip()
                    new_files = st.session_state.get(f"new_files_{n.id}") or []
                    if not new_content:
                        st.error("分析结论内容不能为空")
                    elif len(new_files) > 5:
                        st.error(f"单次最多上传 5 张图片，已选择 {len(new_files)} 张")
                    else:
                        try:
                            with get_session() as session3:
                                update_note(
                                    session3,
                                    note_id=n.id,
                                    user_id=user["id"],
                                    new_content=new_content,
                                    new_added_files=new_files,
                                    removed_image_ids=removed_ids,
                                )
                            st.toast("已更新分析结论", icon="✅")
                            st.session_state.pop(f"edit_{n.id}", None)
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                        except Exception:
                            st.error("操作失败，请稍后重试")
                if save_cols[1].button("取消", key=f"cancel_edit_{n.id}"):
                    st.session_state.pop(f"edit_{n.id}", None)
                    st.rerun()

        # ====== 删除确认框 ======
        if st.session_state.get(f"delete_{n.id}"):
            with st.container(border=True):
                st.warning("⚠️ 确认删除此分析结论？将一并删除所有配图，操作不可恢复。")
                del_cols = st.columns([1, 1, 3])
                if del_cols[0].button("确认删除", key=f"confirm_del_{n.id}", type="primary"):
                    try:
                        with get_session() as session4:
                            delete_note(session4, note_id=n.id, user_id=user["id"])
                        st.toast("已删除分析结论", icon="🗑️")
                        st.session_state.pop(f"delete_{n.id}", None)
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception:
                        st.error("操作失败，请稍后重试")
                if del_cols[1].button("取消", key=f"cancel_del_{n.id}"):
                    st.session_state.pop(f"delete_{n.id}", None)
                    st.rerun()
        st.write("")

st.divider()

# ============================================================
# 添加新分析记录（仅活跃股票可新增；已移出的仅可查看历史）
# ============================================================

if ps_dto.status != "active":
    st.info("⚠️ 该股票已移出股票池，仅可查看历史分析结论，不能新增。")
else:
    st.subheader("添加新分析记录")

    with st.form("add_note_form", clear_on_submit=True):
        new_content = st.text_area(
            "分析结论（必填）",
            key="new_note_content",
            height=120,
        )
        uploaded_files = st.file_uploader(
            "配图（可选，最多 5 张，单张 ≤ 3MB）",
            type=["png", "jpg", "jpeg", "gif", "webp"],
            accept_multiple_files=True,
            key="new_note_files",
        )
        files_valid = True
        if uploaded_files:
            if len(uploaded_files) > 5:
                st.error(f"单次最多上传 5 张图片，已选择 {len(uploaded_files)} 张")
                files_valid = False
            else:
                for f in uploaded_files:
                    ok, msg = validate_image_file(f)
                    if ok:
                        st.caption(f"✅ {f.name} ({f.size / 1024 / 1024:.2f}MB)")
                    else:
                        st.error(f"{f.name}：{msg}")
                        files_valid = False
        submitted = st.form_submit_button("提交分析结论", type="primary")

        if submitted:
            content = (st.session_state.get("new_note_content") or "").strip()
            files = st.session_state.get("new_note_files") or []
            if not content:
                st.error("分析结论内容不能为空")
            elif not files_valid:
                st.error("请修正图片上传后重新提交")
            else:
                try:
                    with get_session() as session5:
                        create_note(
                            session5,
                            pool_stock_id=pool_stock_id,
                            user_id=user["id"],
                            content=content,
                            uploaded_files=files,
                        )
                    st.toast("已添加分析结论", icon="✅")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception:
                    st.error("操作失败，请稍后重试")
