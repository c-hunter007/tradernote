"""股票服务：加入股票池 / 查询池内股票 / Stock 主表缓存。"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import AnalysisNote, PoolStock, Stock, StockPool, User

# ============================================================
# DTO
# ============================================================


@dataclass
class PoolStockDTO:
    id: int  # PoolStock.id
    pool_id: int
    stock_id: int
    code: str  # 6 位代码
    market: str  # SH / SZ / BJ
    name: str
    added_by: int
    added_by_username: str
    added_date: datetime
    initial_analysis: Optional[str]
    is_key_focus: bool
    focus_set_by: Optional[int]
    focus_set_by_username: Optional[str]
    focus_set_at: Optional[datetime]
    status: str  # active / removed
    removed_by: Optional[int] = None
    removed_by_username: Optional[str] = None
    removed_date: Optional[datetime] = None
    removal_analysis: Optional[str] = None
    note_count: int = 0
    pool_name: Optional[str] = None  # 仅复盘归档页使用


# ============================================================
# 查询
# ============================================================


def list_active_pool_stocks(session: Session, pool_id: int) -> list[PoolStockDTO]:
    """列出池内活跃股票。

    排序：is_key_focus DESC, focus_set_at DESC NULLS LAST, added_date DESC
    """
    rows = (
        session.query(PoolStock, Stock, User)
        .join(Stock, PoolStock.stock_id == Stock.id)
        .join(User, PoolStock.added_by == User.id)
        .filter(PoolStock.pool_id == pool_id, PoolStock.status == "active")
        .order_by(
            PoolStock.is_key_focus.desc(),
            PoolStock.focus_set_at.desc().nullslast(),
            PoolStock.added_date.desc(),
        )
        .all()
    )
    if not rows:
        return []

    pool_stock_ids = [ps.id for ps, _, _ in rows]
    note_counts: dict[int, int] = {}
    nc_rows = (
        session.query(AnalysisNote.pool_stock_id, func.count(AnalysisNote.id))
        .filter(AnalysisNote.pool_stock_id.in_(pool_stock_ids))
        .group_by(AnalysisNote.pool_stock_id)
        .all()
    )
    for psid, cnt in nc_rows:
        note_counts[psid] = cnt

    # 一次性查询 focus_set_by 用户名
    focus_user_ids = {ps.focus_set_by for ps, _, _ in rows if ps.focus_set_by}
    focus_users: dict[int, str] = {}
    if focus_user_ids:
        for u in session.query(User).filter(User.id.in_(focus_user_ids)).all():
            focus_users[u.id] = u.username

    return [
        PoolStockDTO(
            id=ps.id,
            pool_id=ps.pool_id,
            stock_id=ps.stock_id,
            code=s.code,
            market=s.market,
            name=s.name,
            added_by=ps.added_by,
            added_by_username=u.username,
            added_date=ps.added_date,
            initial_analysis=ps.initial_analysis,
            is_key_focus=ps.is_key_focus,
            focus_set_by=ps.focus_set_by,
            focus_set_by_username=focus_users.get(ps.focus_set_by) if ps.focus_set_by else None,
            focus_set_at=ps.focus_set_at,
            status=ps.status,
            note_count=note_counts.get(ps.id, 0),
        )
        for ps, s, u in rows
    ]


def get_pool_stock_dto(session: Session, pool_stock_id: int) -> Optional[PoolStockDTO]:
    """获取单个 PoolStock 的 DTO（含 stock、加入者、note 数等）。"""
    row = (
        session.query(PoolStock, Stock, User)
        .join(Stock, PoolStock.stock_id == Stock.id)
        .join(User, PoolStock.added_by == User.id)
        .filter(PoolStock.id == pool_stock_id)
        .first()
    )
    if not row:
        return None
    ps, s, u = row
    note_count = (
        session.query(func.count(AnalysisNote.id))
        .filter(AnalysisNote.pool_stock_id == pool_stock_id)
        .scalar()
        or 0
    )
    focus_username = None
    if ps.focus_set_by:
        fu = session.get(User, ps.focus_set_by)
        if fu:
            focus_username = fu.username
    removed_username = None
    if ps.removed_by:
        ru = session.get(User, ps.removed_by)
        if ru:
            removed_username = ru.username
    return PoolStockDTO(
        id=ps.id,
        pool_id=ps.pool_id,
        stock_id=ps.stock_id,
        code=s.code,
        market=s.market,
        name=s.name,
        added_by=ps.added_by,
        added_by_username=u.username,
        added_date=ps.added_date,
        initial_analysis=ps.initial_analysis,
        is_key_focus=ps.is_key_focus,
        focus_set_by=ps.focus_set_by,
        focus_set_by_username=focus_username,
        focus_set_at=ps.focus_set_at,
        status=ps.status,
        removed_by=ps.removed_by,
        removed_by_username=removed_username,
        removed_date=ps.removed_date,
        removal_analysis=ps.removal_analysis,
        note_count=note_count,
    )


# ============================================================
# Stock 主表缓存
# ============================================================


def get_cached_stock(session: Session, code: str, market: str) -> Optional[Stock]:
    """查询 Stock 表是否已有缓存记录。"""
    return (
        session.query(Stock)
        .filter(Stock.code == code, Stock.market == market)
        .first()
    )


def get_or_create_stock(session: Session, code: str, market: str, name: str) -> Stock:
    """获取或创建 Stock 主表记录。

    - 若 Stock 表已有该 code+market 记录，直接返回（复用缓存名称）
    - 否则新建 Stock 记录
    """
    stock = get_cached_stock(session, code, market)
    if stock:
        return stock
    stock = Stock(code=code, market=market, name=name)
    session.add(stock)
    session.flush()
    return stock


# ============================================================
# 加入股票池
# ============================================================


def is_stock_in_pool(session: Session, pool_id: int, code: str, market: str) -> bool:
    """检查股票是否已在池中（活跃状态）。"""
    stock = get_cached_stock(session, code, market)
    if not stock:
        return False
    return (
        session.query(PoolStock)
        .filter(
            PoolStock.pool_id == pool_id,
            PoolStock.stock_id == stock.id,
            PoolStock.status == "active",
        )
        .first()
        is not None
    )


def add_stock_to_pool_with_market(
    session: Session,
    pool_id: int,
    code: str,
    market: str,
    name: str,
    added_by: int,
    initial_analysis: Optional[str] = None,
) -> PoolStock:
    """加入股票到池（带 market 参数，推荐使用）。

    - 校验：池存在
    - 校验：code/market/name 非空
    - 校验：同一池中不能重复加入同一 code+market 的活跃股票
    - 调用 get_or_create_stock（复用缓存名称）
    """
    pool = session.get(StockPool, pool_id)
    if not pool:
        raise ValueError("股票池不存在")

    code = (code or "").strip()
    market = (market or "").strip().upper()
    name = (name or "").strip()

    if not code:
        raise ValueError("股票代码不能为空")
    if not market:
        raise ValueError("市场不能为空")
    if not name:
        raise ValueError("股票名称不能为空")
    if market not in ("SH", "SZ", "BJ"):
        raise ValueError(f"无效的市场代码：{market}")

    # 检查是否已在池中
    if is_stock_in_pool(session, pool_id, code, market):
        raise ValueError(f"股票 {code} 已在该池中")

    # 获取或创建 Stock 主表记录（复用缓存名称）
    stock = get_or_create_stock(session, code, market, name)

    pool_stock = PoolStock(
        pool_id=pool_id,
        stock_id=stock.id,
        added_by=added_by,
        added_date=datetime.now(),
        initial_analysis=initial_analysis,
        is_key_focus=False,
        status="active",
    )
    session.add(pool_stock)
    session.flush()

    from services.activity_service import record_activity
    record_activity(
        session, added_by, "add_stock",
        f"将 {code} {name} 加入 {pool.name}", pool_id,
    )

    return pool_stock


# ============================================================
# 重点关注 / 移出
# ============================================================


def set_key_focus(
    session: Session,
    pool_stock_id: int,
    user_id: int,
    is_focus: bool,
) -> PoolStock:
    """设置 / 取消重点关注。

    - 校验：pool_stock 存在且 status==active
    - 校验：调用者有权访问该池（can_access_pool）
    - is_focus=True：is_key_focus=True, focus_set_by=user_id, focus_set_at=now
    - is_focus=False：清空 is_key_focus, focus_set_by, focus_set_at（不保留历史）
    """
    ps = session.get(PoolStock, pool_stock_id)
    if not ps:
        raise ValueError("股票池中的股票不存在")
    if ps.status != "active":
        raise ValueError("该股票已移出股票池，无法设置重点关注")

    # 权限校验：调用者必须有权访问该池
    from services.pool_service import can_access_pool
    if not can_access_pool(session, ps.pool_id, user_id):
        raise ValueError("你无权操作该股票池")

    if is_focus:
        ps.is_key_focus = True
        ps.focus_set_by = user_id
        ps.focus_set_at = datetime.now()
    else:
        ps.is_key_focus = False
        ps.focus_set_by = None
        ps.focus_set_at = None
    session.flush()

    from services.activity_service import record_activity
    action = "set_focus" if is_focus else "unset_focus"
    desc = f"将 {ps.stock.code} {ps.stock.name} 设为重点关注" if is_focus else f"取消 {ps.stock.code} {ps.stock.name} 的重点关注"
    record_activity(session, user_id, action, desc, ps.pool_id)

    return ps


def remove_stock_from_pool(
    session: Session,
    pool_stock_id: int,
    removed_by: int,
    removal_analysis: str,
) -> PoolStock:
    """移出股票池（软删除，保留记录供复盘）。

    - 校验：pool_stock 存在且 status==active
    - 校验：调用者有权访问该池
    - 校验：removal_analysis 非空（M4 决策：必填）
    - 设置 status='removed', removed_by, removed_date=now, removal_analysis
    - 同时清空重点关注状态（已移出的不再重点）
    """
    ps = session.get(PoolStock, pool_stock_id)
    if not ps:
        raise ValueError("股票池中的股票不存在")
    if ps.status != "active":
        raise ValueError("该股票已移出股票池")

    # 权限校验
    from services.pool_service import can_access_pool
    if not can_access_pool(session, ps.pool_id, removed_by):
        raise ValueError("你无权操作该股票池")

    analysis = (removal_analysis or "").strip()
    if not analysis:
        raise ValueError("移出分析结论不能为空（必填）")

    ps.status = "removed"
    ps.removed_by = removed_by
    ps.removed_date = datetime.now()
    ps.removal_analysis = analysis
    # 同时清空重点关注状态
    ps.is_key_focus = False
    ps.focus_set_by = None
    ps.focus_set_at = None
    session.flush()

    from services.activity_service import record_activity
    record_activity(
        session, removed_by, "remove_stock",
        f"将 {ps.stock.code} {ps.stock.name} 移出 {ps.pool.name}", ps.pool_id,
    )

    return ps


# ============================================================
# 复盘归档查询
# ============================================================


def _build_dto_from_row(
    ps: PoolStock,
    s: Stock,
    u: User,
    note_count: int,
    focus_username: Optional[str] = None,
    removed_username: Optional[str] = None,
    pool_name: Optional[str] = None,
) -> PoolStockDTO:
    """从查询行构造 DTO（复用）。"""
    return PoolStockDTO(
        id=ps.id,
        pool_id=ps.pool_id,
        stock_id=ps.stock_id,
        code=s.code,
        market=s.market,
        name=s.name,
        added_by=ps.added_by,
        added_by_username=u.username,
        added_date=ps.added_date,
        initial_analysis=ps.initial_analysis,
        is_key_focus=ps.is_key_focus,
        focus_set_by=ps.focus_set_by,
        focus_set_by_username=focus_username,
        focus_set_at=ps.focus_set_at,
        status=ps.status,
        removed_by=ps.removed_by,
        removed_by_username=removed_username,
        removed_date=ps.removed_date,
        removal_analysis=ps.removal_analysis,
        note_count=note_count,
        pool_name=pool_name,
    )


def list_removed_pool_stocks(session: Session, pool_id: int) -> list[PoolStockDTO]:
    """列出某池中已移出的股票（按 removed_date 倒序）。"""
    rows = (
        session.query(PoolStock, Stock, User)
        .join(Stock, PoolStock.stock_id == Stock.id)
        .join(User, PoolStock.added_by == User.id)
        .filter(PoolStock.pool_id == pool_id, PoolStock.status == "removed")
        .order_by(PoolStock.removed_date.desc().nullslast())
        .all()
    )
    return _fill_removed_dtos(session, rows)


def list_all_removed_stocks_for_user(session: Session, user_id: int) -> list[PoolStockDTO]:
    """列出当前用户可见的所有已移出股票（跨所有池）。

    - 私有池：creator_id == user_id
    - 共享池：creator_id == user_id 或在 pool_members 表中
    - 按 removed_date 倒序
    """
    from database.models import PoolMember
    member_pool_ids = select(PoolMember.pool_id).where(PoolMember.user_id == user_id).subquery()

    rows = (
        session.query(PoolStock, Stock, User)
        .join(Stock, PoolStock.stock_id == Stock.id)
        .join(User, PoolStock.added_by == User.id)
        .join(StockPool, PoolStock.pool_id == StockPool.id)
        .filter(
            PoolStock.status == "removed",
            (StockPool.creator_id == user_id)
            | (PoolStock.pool_id.in_(select(member_pool_ids.c.pool_id))),
        )
        .order_by(PoolStock.removed_date.desc().nullslast())
        .all()
    )
    return _fill_removed_dtos(session, rows, with_pool_name=True)


def _fill_removed_dtos(
    session: Session,
    rows: list,
    with_pool_name: bool = False,
) -> list[PoolStockDTO]:
    """填充已移出股票的 DTO 列表（含 note 数、移出者用户名、池名）。"""
    if not rows:
        return []

    pool_stock_ids = [ps.id for ps, _, _ in rows]
    pool_ids = {ps.pool_id for ps, _, _ in rows}

    # note 数
    note_counts: dict[int, int] = {}
    nc_rows = (
        session.query(AnalysisNote.pool_stock_id, func.count(AnalysisNote.id))
        .filter(AnalysisNote.pool_stock_id.in_(pool_stock_ids))
        .group_by(AnalysisNote.pool_stock_id)
        .all()
    )
    for psid, cnt in nc_rows:
        note_counts[psid] = cnt

    # 移出者用户名
    removed_user_ids = {ps.removed_by for ps, _, _ in rows if ps.removed_by}
    removed_users: dict[int, str] = {}
    if removed_user_ids:
        for u in session.query(User).filter(User.id.in_(removed_user_ids)).all():
            removed_users[u.id] = u.username

    # 池名
    pool_names: dict[int, str] = {}
    if with_pool_name and pool_ids:
        for p in session.query(StockPool).filter(StockPool.id.in_(pool_ids)).all():
            pool_names[p.id] = p.name

    return [
        _build_dto_from_row(
            ps, s, u,
            note_count=note_counts.get(ps.id, 0),
            removed_username=removed_users.get(ps.removed_by) if ps.removed_by else None,
            pool_name=pool_names.get(ps.pool_id) if with_pool_name else None,
        )
        for ps, s, u in rows
    ]


# ============================================================
# 仪表盘统计
# ============================================================


def _user_visible_pool_ids_subquery(user_id: int):
    """返回用户可见池 ID 的子查询（私有池 + 共享池成员）。"""
    from database.models import PoolMember
    member_pool_ids = select(PoolMember.pool_id).where(PoolMember.user_id == user_id).subquery()
    return (
        select(StockPool.id).where(
            (StockPool.creator_id == user_id)
            | (StockPool.id.in_(select(member_pool_ids.c.pool_id)))
        )
    )


def count_active_stocks_for_user(session: Session, user_id: int) -> int:
    """统计用户可见池中的活跃股票总数。"""
    visible_pool_ids = _user_visible_pool_ids_subquery(user_id)
    return (
        session.query(func.count(PoolStock.id))
        .filter(
            PoolStock.pool_id.in_(visible_pool_ids),
            PoolStock.status == "active",
        )
        .scalar()
        or 0
    )


def count_key_focus_stocks_for_user(session: Session, user_id: int) -> int:
    """统计用户可见池中的重点关注股票数。"""
    visible_pool_ids = _user_visible_pool_ids_subquery(user_id)
    return (
        session.query(func.count(PoolStock.id))
        .filter(
            PoolStock.pool_id.in_(visible_pool_ids),
            PoolStock.status == "active",
            PoolStock.is_key_focus.is_(True),
        )
        .scalar()
        or 0
    )


def count_total_notes_for_user(session: Session, user_id: int) -> int:
    """统计用户可见池中的分析结论总数。"""
    visible_pool_ids = _user_visible_pool_ids_subquery(user_id)
    return (
        session.query(func.count(AnalysisNote.id))
        .join(PoolStock, AnalysisNote.pool_stock_id == PoolStock.id)
        .filter(PoolStock.pool_id.in_(visible_pool_ids))
        .scalar()
        or 0
    )
