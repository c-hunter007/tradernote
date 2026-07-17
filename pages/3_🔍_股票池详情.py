"""股票池详情：池内股票列表 + 加入股票弹窗 + 重点标记 + 移出。"""
import streamlit as st

from database.db import get_session
from services.akshare_service import (
    detect_market,
    fetch_stock_name_from_akshare,
    validate_code,
)
from services.pool_service import can_access_pool, get_pool_dto
from services.stock_service import (
    add_stock_to_pool_with_market,
    get_cached_stock,
    is_stock_in_pool,
    list_active_pool_stocks,
    remove_stock_from_pool,
    set_key_focus,
)
from utils.date_util import format_date
from utils.page import render_back_to_pools_button, render_page_header, render_sidebar_user
from utils.ui import render_empty_state, render_stock_card

user = render_page_header("股票池详情", "🔍", "查看与维护池内股票")
render_sidebar_user()

# ============================================================
# 读取 URL 参数
# ============================================================

pool_id_str = st.session_state.get("pool_id")
if not pool_id_str:
    st.info("📍 此页面需要从「我的股票池」进入。\n\n请先前往「我的股票池」选择一个股票池，再点击「进入详情」。")
    render_back_to_pools_button()
    st.stop()

try:
    pool_id = int(pool_id_str)
except ValueError:
    st.error("无效的股票池 ID。")
    render_back_to_pools_button()
    st.stop()

# ============================================================
# 校验池存在 & 访问权限
# ============================================================

with get_session() as session:
    pool_dto = get_pool_dto(session, pool_id)
    if not pool_dto:
        st.error("股票池不存在或已被删除。")
        render_back_to_pools_button()
        st.stop()

    if not can_access_pool(session, pool_id, user["id"]):
        st.error("你无权访问该股票池。")
        render_back_to_pools_button()
        st.stop()

# 顶部信息
st.subheader(f"📋 {pool_dto.name}")
type_label = "👥 共享池" if pool_dto.type == "shared" else "🔒 私有池"
st.caption(
    f"类型：{type_label} · "
    f"创建者：{pool_dto.creator_username} · 创建于 {format_date(pool_dto.created_at)} · "
    f"在池股票：{pool_dto.active_stock_count}"
)

col_back, col_member, col_spacer, col_add = st.columns([1, 1, 3, 1])
with col_back:
    render_back_to_pools_button()
if pool_dto.type == "shared":
    with col_member:
        if st.button("⚙️ 管理设置"):
            st.session_state["pool_id"] = pool_id
            st.switch_page(st.session_state["_page_members"])
with col_add:
    if st.button("➕ 加入股票", type="primary", use_container_width=True):
        st.session_state["show_add_dialog"] = True
        st.rerun()

st.divider()

# ============================================================
# 加入股票弹窗
# ============================================================


@st.dialog("加入股票", width="small")
def _add_stock_dialog():
    st.caption(f"加入股票到「{pool_dto.name}」")

    # 自动查询名称（on_change 触发）
    def _on_code_change():
        raw = (st.session_state.get("add_stock_code") or "").strip()
        st.session_state["add_stock_query_result"] = None
        st.session_state["add_stock_name"] = ""
        st.session_state["add_stock_market"] = ""
        st.session_state["add_stock_manual"] = False
        st.session_state["add_stock_error"] = ""

        if not raw:
            return
        if not validate_code(raw):
            st.session_state["add_stock_error"] = "请输入 6 位数字代码"
            return
        market = detect_market(raw)
        if market is None:
            st.session_state["add_stock_error"] = "无法识别该代码所属市场"
            return

        # 先查 Stock 表缓存
        with get_session() as session:
            cached = get_cached_stock(session, raw, market)
            if cached:
                st.session_state["add_stock_query_result"] = cached.name
                st.session_state["add_stock_name"] = cached.name
                st.session_state["add_stock_market"] = market
                return
            # 检查是否已在池中
            if is_stock_in_pool(session, pool_id, raw, market):
                st.session_state["add_stock_error"] = f"股票 {raw} 已在该池中"
                return

        # 调用 akshare
        with st.spinner("正在通过 akshare 查询股票名称..."):
            name = fetch_stock_name_from_akshare(raw)
        if name:
            st.session_state["add_stock_query_result"] = name
            st.session_state["add_stock_name"] = name
            st.session_state["add_stock_market"] = market
        else:
            st.session_state["add_stock_error"] = "akshare 查询失败，请手工输入名称"
            st.session_state["add_stock_manual"] = True
            st.session_state["add_stock_market"] = market

    code = st.text_input(
        "股票代码（6 位数字）",
        max_chars=6,
        key="add_stock_code",
        help="例如：600519（上交所）/ 000001（深交所）/ 430047（北交所）",
        on_change=_on_code_change,
    )

    # 显示查询结果或错误
    if st.session_state.get("add_stock_error"):
        st.error(st.session_state["add_stock_error"])

    market = st.session_state.get("add_stock_market", "")
    name = st.session_state.get("add_stock_name", "")
    manual = st.session_state.get("add_stock_manual", False)

    if manual:
        st.warning(f"⚠️ akshare 查询失败，市场：{market}，请手工输入名称")
        name = st.text_input("股票名称（手工输入）", value="", key="add_stock_name_manual")
    elif market and name:
        st.success(f"✅ {code} · {name} · 市场：{market}")

    initial_analysis = st.text_area(
        "初始分析结论（可选）",
        key="add_stock_initial",
        height=100,
        help="记录你发现该股票时的分析结论，可留空稍后补充",
    )

    col_cancel, col_confirm = st.columns(2)
    if col_cancel.button("取消", use_container_width=True):
        for k in (
            "add_stock_code",
            "add_stock_query_result",
            "add_stock_name",
            "add_stock_market",
            "add_stock_manual",
            "add_stock_error",
            "add_stock_initial",
            "add_stock_name_manual",
        ):
            st.session_state.pop(k, None)
        st.rerun()

    if col_confirm.button("确认加入", type="primary", use_container_width=True):
        raw_code = (st.session_state.get("add_stock_code") or "").strip()
        final_market = st.session_state.get("add_stock_market", "")
        if st.session_state.get("add_stock_manual"):
            final_name = (st.session_state.get("add_stock_name_manual") or "").strip()
        else:
            final_name = (st.session_state.get("add_stock_name") or "").strip()
        initial = (st.session_state.get("add_stock_initial") or "").strip() or None

        if not validate_code(raw_code):
            st.error("请输入有效的 6 位数字代码")
        elif not final_market:
            st.error("无法识别市场，请重新输入代码")
        elif not final_name:
            st.error("股票名称不能为空")
        else:
            try:
                with get_session() as session:
                    add_stock_to_pool_with_market(
                        session,
                        pool_id=pool_id,
                        code=raw_code,
                        market=final_market,
                        name=final_name,
                        added_by=user["id"],
                        initial_analysis=initial,
                    )
                st.toast(f"已加入股票 {raw_code} {final_name}", icon="✅")
                for k in (
                    "add_stock_code",
                    "add_stock_query_result",
                    "add_stock_name",
                    "add_stock_market",
                    "add_stock_manual",
                    "add_stock_error",
                    "add_stock_initial",
                    "add_stock_name_manual",
                ):
                    st.session_state.pop(k, None)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error("操作失败，请稍后重试")


# 弹窗触发逻辑
if st.session_state.get("show_add_dialog"):
    st.session_state.pop("show_add_dialog", None)
    _add_stock_dialog()


# ============================================================
# 移出股票弹窗
# ============================================================


@st.dialog("移出股票", width="small")
def _remove_stock_dialog(pool_stock_id: int, code: str, name: str, market: str):
    st.caption(f"将以下股票移出「{pool_dto.name}」：")
    st.markdown(f"**{code} {name} · {market}**")
    st.warning("移出后该股票将从池中消失，但可在「复盘归档」页查看。")
    removal_analysis = st.text_area(
        "移出分析结论（必填）",
        key=f"removal_analysis_{pool_stock_id}",
        height=100,
        help="请记录移出原因，便于后续复盘分析",
    )
    col_cancel, col_confirm = st.columns(2)
    if col_cancel.button("取消", use_container_width=True):
        st.session_state.pop(f"removal_analysis_{pool_stock_id}", None)
        st.session_state.pop("remove_target", None)
        st.rerun()
    if col_confirm.button("确认移出", type="primary", use_container_width=True):
        analysis = (st.session_state.get(f"removal_analysis_{pool_stock_id}") or "").strip()
        if not analysis:
            st.error("移出分析结论不能为空（必填）")
        else:
            try:
                with get_session() as session:
                    remove_stock_from_pool(
                        session,
                        pool_stock_id=pool_stock_id,
                        removed_by=user["id"],
                        removal_analysis=analysis,
                    )
                st.toast(f"已移出股票 {code} {name}", icon="📤")
                st.session_state.pop(f"removal_analysis_{pool_stock_id}", None)
                st.session_state.pop("remove_target", None)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error("操作失败，请稍后重试")


# 移出弹窗触发逻辑
remove_target = st.session_state.get("remove_target")
if remove_target:
    st.session_state.pop("remove_target", None)
    _remove_stock_dialog(
        pool_stock_id=remove_target["id"],
        code=remove_target["code"],
        name=remove_target["name"],
        market=remove_target["market"],
    )

# ============================================================
# 池内股票列表
# ============================================================

with get_session() as session:
    stocks = list_active_pool_stocks(session, pool_id)

if not stocks:
    render_empty_state("暂无股票，点击右上角「加入股票」开始跟踪", icon="📊")
else:
    for s in stocks:
        render_stock_card(
            code=s.code,
            name=s.name,
            market=s.market,
            added_date=format_date(s.added_date),
            added_by_username=s.added_by_username,
            initial_analysis=s.initial_analysis,
            note_count=s.note_count,
            is_key_focus=s.is_key_focus,
        )
        col_view, col_focus, col_remove, _ = st.columns([1, 1, 1, 2])
        with col_view:
            if st.button("📝 查看分析", key=f"view_{s.id}", use_container_width=True):
                st.session_state["pool_stock_id"] = s.id
                st.switch_page(st.session_state["_hidden_analysis_page"])
        with col_focus:
            if s.is_key_focus:
                if st.button("☆ 取消重点", key=f"unfocus_{s.id}", use_container_width=True):
                    try:
                        with get_session() as session:
                            set_key_focus(
                                session,
                                pool_stock_id=s.id,
                                user_id=user["id"],
                                is_focus=False,
                            )
                        st.toast(f"已取消重点关注 {s.code}", icon="💫")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception:
                        st.error("操作失败，请稍后重试")
            else:
                if st.button("⭐ 设为重点", key=f"focus_{s.id}", use_container_width=True):
                    try:
                        with get_session() as session:
                            set_key_focus(
                                session,
                                pool_stock_id=s.id,
                                user_id=user["id"],
                                is_focus=True,
                            )
                        st.toast(f"已设为重点关注 {s.code}", icon="⭐")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception:
                        st.error("操作失败，请稍后重试")
        with col_remove:
            if st.button("📤 移出", key=f"remove_{s.id}", use_container_width=True):
                st.session_state["remove_target"] = {
                    "id": s.id,
                    "code": s.code,
                    "name": s.name,
                    "market": s.market,
                }
                st.rerun()
        st.write("")
