"""交易记录：持仓管理、买卖操作、统计分析。"""
from datetime import date, datetime, timedelta

import streamlit as st

from database.db import get_session
from services.trading_service import (
    TradingAccount,
    buy_stock,
    get_or_create_account,
    get_positions,
    get_statistics,
    get_trade_history,
    lookup_stock_name,
    reset_account,
    sell_stock,
    update_account,
)
from utils.date_util import format_date
from utils.page import render_page_header, render_sidebar_user
from utils.ui import render_empty_state

user = render_page_header("交易记录", "🚧", "持仓管理、买卖操作与统计分析")
render_sidebar_user()


# ============================================================
# 初始设定对话框
# ============================================================


def _render_initial_setup():
    st.subheader("🔧 初始设定")
    st.caption("设置账户信息后即可开始使用交易记录功能。")
    st.markdown("---")

    funds = st.number_input("可用资金（元）", min_value=0.0, format="%.2f", key="setup_funds")
    rate = st.number_input(
        "交易费率",
        min_value=0.0,
        max_value=0.01,
        value=0.0003,
        format="%.6f",
        key="setup_rate",
        help="例：0.0003 表示万分之三",
    )

    st.markdown("---")
    st.markdown("**当前持仓（可选）**")

    if "setup_holdings" not in st.session_state:
        st.session_state["setup_holdings"] = []

    if st.session_state["setup_holdings"]:
        hcols = st.columns([1.5, 1.5, 1, 1, 1, 0.5])
        hcols[0].markdown("**股票代码**")
        hcols[1].markdown("**股票名称**")
        hcols[2].markdown("**买入价**")
        hcols[3].markdown("**数量**")
        hcols[4].markdown("**买入日**")
        hcols[5].markdown("**操作**")

    for i, h in enumerate(st.session_state["setup_holdings"]):
        with st.container(border=True):
            c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.5, 1, 1, 1, 0.5])
            h["code"] = c1.text_input(
                "股票代码", value=h.get("code", ""), max_chars=6, key=f"sh_code_{i}",
                label_visibility="collapsed",
            )
            code = h["code"]
            if code and len(code) == 6 and code.isdigit():
                name = lookup_stock_name(code)
                if name:
                    h["name"] = name
                    st.session_state[f"sh_name_{i}"] = name
            h["name"] = c2.text_input(
                "股票名称", value=h.get("name", ""), key=f"sh_name_{i}",
                label_visibility="collapsed",
            )
            h["price"] = c3.number_input(
                "买入价", value=float(h.get("price", 0.0)), format="%.2f",
                key=f"sh_price_{i}", label_visibility="collapsed",
            )
            h["qty"] = c4.number_input(
                "数量", value=int(h.get("qty", 0)), min_value=0,
                key=f"sh_qty_{i}", label_visibility="collapsed",
            )
            h["date"] = c5.date_input(
                "买入日", value=h.get("date", date.today()),
                key=f"sh_date_{i}", label_visibility="collapsed",
            )
            if c6.button("✕", key=f"sh_del_{i}"):
                holdings = st.session_state["setup_holdings"]
                st.session_state["setup_holdings"] = holdings[:i] + holdings[i + 1:]
                st.rerun()

    if st.button("➕ 添加持仓"):
        st.session_state["setup_holdings"] = st.session_state["setup_holdings"] + [
            {"code": "", "name": "", "price": 0.0, "qty": 0, "date": date.today()}
        ]
        st.rerun()

    st.markdown("---")
    if st.button("💾 保存初始设定", type="primary", use_container_width=True):
        if funds < 0:
            st.error("可用资金不能为负数")
            return
        if rate < 0:
            st.error("交易费率不能为负数")
            return

        for h in st.session_state["setup_holdings"]:
            code = h.get("code", "").strip()
            name = h.get("name", "").strip()
            price = float(h.get("price", 0))
            qty = int(h.get("qty", 0))
            if not code or not name or price <= 0 or qty <= 0:
                st.error("请完整填写所有持仓信息")
                return

        with get_session() as session:
            update_account(session, user["id"], funds, rate)
            for h in st.session_state["setup_holdings"]:
                code = h["code"].strip()
                name = h["name"].strip()
                price = float(h["price"])
                qty = int(h["qty"])
                td = h["date"]
                buy_stock(session, user["id"], code, name, price, qty, td, is_initial=True)

        for k in list(st.session_state.keys()):
            if k.startswith("setup_") or k.startswith("sh_"):
                del st.session_state[k]
        st.session_state.pop("setup_holdings", None)
        st.toast("初始设定完成", icon="✅")
        st.rerun()


# ============================================================
# 买入对话框
# ============================================================


@st.dialog("买入股票", width="small")
def _buy_dialog():
    code = st.text_input("股票代码（6 位数字）", max_chars=6, key="buy_code")
    stock_name = ""
    if code and len(code) == 6 and code.isdigit():
        stock_name = lookup_stock_name(code)
        if stock_name:
            st.session_state["buy_name"] = stock_name
    if stock_name:
        st.success(f"✅ {stock_name}")
    else:
        st.caption("未找到股票名称，请确认代码")

    stock_name_manual = st.text_input("股票名称", value="", key="buy_name")
    price = st.number_input("买入价格", min_value=0.01, format="%.2f", key="buy_price")
    quantity = st.number_input("买入数量", min_value=100, step=100, key="buy_qty")
    trade_date = st.date_input("买入日期", value=date.today(), key="buy_date")

    col_cancel, col_confirm = st.columns(2)
    if col_cancel.button("取消", use_container_width=True):
        st.rerun()
    if col_confirm.button("确认买入", type="primary", use_container_width=True):
        raw_code = (code or "").strip()
        final_name = (stock_name_manual or stock_name or "").strip()
        if not raw_code or len(raw_code) != 6 or not raw_code.isdigit():
            st.error("请输入有效的 6 位数字股票代码")
        elif not final_name:
            st.error("股票名称不能为空")
        elif price <= 0:
            st.error("买入价格必须大于 0")
        elif quantity <= 0:
            st.error("买入数量必须大于 0")
        else:
            try:
                with get_session() as session:
                    buy_stock(session, user["id"], raw_code, final_name, price, quantity, trade_date)
                st.toast(f"已买入 {raw_code} {final_name} {quantity} 股", icon="✅")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error("操作失败，请稍后重试")


# ============================================================
# 卖出对话框
# ============================================================


@st.dialog("卖出股票", width="small")
def _sell_dialog(stock_code: str, stock_name: str, avg_price: float, max_qty: int, buy_date: date):
    st.caption(f"{stock_code} {stock_name}")
    st.markdown(f"**持仓均价**：¥{avg_price:.2f}　**可卖数量**：{max_qty} 股")

    price = st.number_input("卖出价格", min_value=0.01, format="%.2f", key="sell_price")
    quantity = st.number_input(
        "卖出数量", min_value=100, max_value=max_qty, step=100, value=max_qty, key="sell_qty"
    )
    trade_date = st.date_input("卖出日期", value=date.today(), key="sell_date")

    earliest = buy_date + timedelta(days=1)
    if trade_date <= buy_date:
        st.warning(f"⚠️ T+1 限制：最早可卖日期为 {format_date(earliest)}")

    col_cancel, col_confirm = st.columns(2)
    if col_cancel.button("取消", use_container_width=True):
        st.rerun()
    if col_confirm.button("确认卖出", type="primary", use_container_width=True):
        if price <= 0:
            st.error("卖出价格必须大于 0")
        elif quantity <= 0 or quantity > max_qty:
            st.error(f"卖出数量须在 1~{max_qty} 之间")
        elif trade_date <= buy_date:
            st.error(f"卖出日期不能早于买入日期的次日（T+1），最早可卖日为 {format_date(earliest)}")
        else:
            try:
                with get_session() as session:
                    record = sell_stock(session, user["id"], stock_code, price, quantity, trade_date)
                    sell_pnl = record.pnl
                msg = f"已卖出 {stock_code} {quantity} 股"
                if sell_pnl is not None:
                    msg += f"，盈亏：¥{sell_pnl:+.2f}"
                st.toast(msg, icon="✅")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error("操作失败，请稍后重试")


# ============================================================
# 区域一：持仓与资金
# ============================================================


def _render_holdings_area() -> None:
    st.subheader("💰 持仓与资金")

    with get_session() as session:
        account = get_or_create_account(session, user["id"])
        positions_raw = get_positions(session, user["id"])
        available_funds = account.available_funds
        commission_rate = account.commission_rate
        positions = [
            {
                "stock_code": p.stock_code,
                "stock_name": p.stock_name,
                "avg_price": p.avg_price,
                "quantity": p.quantity,
                "total_buy_cost": p.total_buy_cost,
                "buy_date": p.buy_date,
            }
            for p in positions_raw
        ]

    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    col1.metric("可用资金", f"¥{available_funds:,.2f}")
    col2.metric("交易费率", f"{commission_rate * 100:.3f}%")
    if col3.button("➕ 买入", type="primary", use_container_width=True):
        _buy_dialog()
    if col4.button("🔄 重置", use_container_width=True):
        st.session_state["confirm_reset"] = True
        st.rerun()

    if st.session_state.get("confirm_reset"):
        with st.container(border=True):
            st.warning("⚠️ 确认重置初始设定？将删除所有交易数据，操作不可恢复。")
            cc1, cc2, _ = st.columns([1, 1, 3])
            if cc1.button("确认重置", type="primary", key="confirm_reset_btn"):
                with get_session() as session:
                    reset_account(session, user["id"])
                st.toast("已重置初始设定", icon="🗑️")
                st.session_state.pop("confirm_reset", None)
                st.rerun()
            if cc2.button("取消", key="cancel_reset_btn"):
                st.session_state.pop("confirm_reset", None)
                st.rerun()

    if not positions:
        render_empty_state("暂无持仓，点击「买入」按钮开始交易", icon="📭")
    else:
        for pos in positions:
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1, 1, 1])
                cols[0].markdown(f"**{pos['stock_code']}** {pos['stock_name']}")
                cols[1].markdown(f"买入均价：¥{pos['avg_price']:.2f}")
                cols[2].markdown(f"买入日期：{format_date(pos['buy_date'])}")
                cols[3].markdown(f"持仓：{pos['quantity']} 股")
                cols[4].markdown(f"总成本：¥{pos['total_buy_cost']:,.2f}")
                if cols[5].button("卖出", key=f"sell_{pos['stock_code']}", use_container_width=True):
                    _sell_dialog(
                        pos['stock_code'],
                        pos['stock_name'],
                        pos['avg_price'],
                        pos['quantity'],
                        pos['buy_date'],
                    )


# ============================================================
# 区域二：交易统计分析
# ============================================================


def _render_statistics_area() -> None:
    st.subheader("📊 交易统计分析")

    today = date.today()
    default_start = today - timedelta(days=365)
    date_range = st.date_input(
        "统计时段",
        value=(default_start, today),
        key="stats_date_range",
    )

    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = default_start, today

    with get_session() as session:
        stats = get_statistics(session, user["id"], start_date, end_date)

    if stats.total_trades == 0:
        render_empty_state("统计时段内无已完成交易", icon="📊")
        return

    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)

    with c1:
        st.metric("盈利次数占比", f"{stats.win_rate * 100:.1f}%", help=f"{stats.win_count}/{stats.total_trades}")
    with c2:
        st.metric("总盈亏", f"¥{stats.total_pnl:+,.2f}")
    with c3:
        st.metric("收益率", f"{stats.return_rate * 100:+.2f}%")
    with c4:
        st.metric("单笔最大盈利", f"¥{stats.max_profit:+,.2f}")
    with c5:
        st.metric("单笔最大亏损", f"¥{stats.max_loss:+,.2f}")
    with c6:
        st.metric("最大连续亏损", f"{stats.max_consecutive_losses} 次")


# ============================================================
# 区域三：详细交易记录
# ============================================================


def _render_trade_history_area() -> None:
    st.subheader("📋 详细交易记录")

    page = st.session_state.get("trade_page", 1)
    with get_session() as session:
        result = get_trade_history(session, user["id"], page=page, page_size=5)
        records = [
            {
                "trade_date": r.trade_date,
                "trade_type": r.trade_type,
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "price": r.price,
                "quantity": r.quantity,
                "pnl": r.pnl,
                "commission": r.commission,
            }
            for r in result.records
        ]

    if result.total == 0:
        render_empty_state("暂无交易记录", icon="📋")
        return

    st.caption(f"共 {result.total} 笔交易")

    header = st.columns([2, 1, 1.5, 1.5, 1, 1, 1])
    header[0].markdown("**日期**")
    header[1].markdown("**类型**")
    header[2].markdown("**代码**")
    header[3].markdown("**名称**")
    header[4].markdown("**价格**")
    header[5].markdown("**数量**")
    header[6].markdown("**盈亏**")
    st.divider()

    for r in records:
        cols = st.columns([2, 1, 1.5, 1.5, 1, 1, 1])
        cols[0].write(format_date(r["trade_date"]))
        type_label = "🟢 买入" if r["trade_type"] == "buy" else "🔴 卖出"
        cols[1].write(type_label)
        cols[2].write(r["stock_code"])
        cols[3].write(r["stock_name"])
        cols[4].write(f"¥{r['price']:.2f}")
        cols[5].write(f"{r['quantity']}")
        if r["pnl"] is not None:
            color = "green" if r["pnl"] >= 0 else "red"
            cols[6].markdown(f":{color}[¥{r['pnl']:+,.2f}]")
        else:
            cols[6].write("—")
        if r["commission"] > 0:
            cols[6].caption(f"佣金 ¥{r['commission']:.2f}")

    st.divider()

    if result.total_pages > 1:
        col_prev, col_info, col_next = st.columns([1, 3, 1])
        with col_prev:
            if result.page > 1:
                if st.button("← 上一页", use_container_width=True):
                    st.session_state["trade_page"] = result.page - 1
                    st.rerun()
        with col_info:
            st.markdown(
                f"<div style='text-align:center;'>第 {result.page}/{result.total_pages} 页</div>",
                unsafe_allow_html=True,
            )
        with col_next:
            if result.page < result.total_pages:
                if st.button("下一页 →", use_container_width=True):
                    st.session_state["trade_page"] = result.page + 1
                    st.rerun()


# ============================================================
# 主流程
# ============================================================

with get_session() as session:
    account = session.get(TradingAccount, user["id"])

if account is None:
    _render_initial_setup()
else:
    _render_holdings_area()
    st.divider()
    _render_statistics_area()
    st.divider()
    _render_trade_history_area()