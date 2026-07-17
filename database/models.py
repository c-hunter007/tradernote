"""SQLAlchemy ORM 模型定义。"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """用户表。

    role: admin / user
    is_active: 是否启用（False 表示禁用账号）
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default="user")  # admin / user
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("(datetime('now','localtime'))"))

    created_by_user = relationship("User", remote_side=[id], backref="created_users")


class StockPool(Base):
    """股票池。

    type: private / shared
    """

    __tablename__ = "stock_pools"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    type = Column(String(16), nullable=False)  # private / shared
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    feishu_webhook = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("(datetime('now','localtime'))"))

    creator = relationship("User", backref="created_pools")
    members = relationship("PoolMember", back_populates="pool", cascade="all, delete-orphan")
    pool_stocks = relationship("PoolStock", back_populates="pool", cascade="all, delete-orphan")


class PoolMember(Base):
    """共享股票池成员（仅共享池使用）。

    role: owner / member
    """

    __tablename__ = "pool_members"
    __table_args__ = (UniqueConstraint("pool_id", "user_id", name="uq_pool_user"),)

    id = Column(Integer, primary_key=True)
    pool_id = Column(Integer, ForeignKey("stock_pools.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(16), nullable=False)  # owner / member
    added_at = Column(DateTime, nullable=False, server_default=text("(datetime('now','localtime'))"))

    pool = relationship("StockPool", back_populates="members")
    user = relationship("User", backref="pool_memberships")


class Stock(Base):
    """股票主表（避免重复，名称缓存）。

    code: 6 位代码（不含后缀）
    market: SH / SZ / BJ
    name: 由 akshare 缓存
    """

    __tablename__ = "stocks"
    __table_args__ = (UniqueConstraint("code", "market", name="uq_code_market"),)

    id = Column(Integer, primary_key=True)
    code = Column(String(6), nullable=False)
    market = Column(String(2), nullable=False)
    name = Column(String(64), nullable=False)
    cached_at = Column(DateTime, nullable=False, server_default=text("(datetime('now','localtime'))"))

    pool_stocks = relationship("PoolStock", back_populates="stock")


class PoolStock(Base):
    """股票池中的股票关联表。

    status: active / removed
    is_key_focus: 是否重点关注
    added_date / removed_date: 日期时间（展示时按 YYYY-MM-DD 格式化）
    """

    __tablename__ = "pool_stocks"

    id = Column(Integer, primary_key=True)
    pool_id = Column(Integer, ForeignKey("stock_pools.id"), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    added_date = Column(DateTime, nullable=False, server_default=text("(datetime('now','localtime'))"))
    initial_analysis = Column(Text, nullable=True)
    is_key_focus = Column(Boolean, nullable=False, default=False)
    focus_set_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    focus_set_at = Column(DateTime, nullable=True)
    status = Column(String(16), nullable=False, default="active")  # active / removed
    removed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    removed_date = Column(DateTime, nullable=True)
    removal_analysis = Column(Text, nullable=True)

    pool = relationship("StockPool", back_populates="pool_stocks")
    stock = relationship("Stock", back_populates="pool_stocks")
    added_by_user = relationship("User", foreign_keys=[added_by], backref="added_stocks")
    focus_set_by_user = relationship("User", foreign_keys=[focus_set_by])
    removed_by_user = relationship("User", foreign_keys=[removed_by])
    notes = relationship("AnalysisNote", back_populates="pool_stock", cascade="all, delete-orphan")


class AnalysisNote(Base):
    """股票分析结论（每次添加一条）。"""

    __tablename__ = "analysis_notes"

    id = Column(Integer, primary_key=True)
    pool_stock_id = Column(Integer, ForeignKey("pool_stocks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("(datetime('now','localtime'))"))

    pool_stock = relationship("PoolStock", back_populates="notes")
    user = relationship("User", backref="notes")
    images = relationship("AnalysisImage", back_populates="note", cascade="all, delete-orphan")
    comments = relationship("NoteComment", back_populates="note", cascade="all, delete-orphan")


class AnalysisImage(Base):
    """分析结论配图（DB 仅存路径）。"""

    __tablename__ = "analysis_images"

    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("analysis_notes.id"), nullable=False)
    file_path = Column(String(512), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=text("(datetime('now','localtime'))"))

    note = relationship("AnalysisNote", back_populates="images")


class Activity(Base):
    """活动日志（仪表盘「近期活动」用）。"""

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pool_id = Column(Integer, ForeignKey("stock_pools.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(32), nullable=False)
    description = Column(String(512), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("(datetime('now','localtime'))"))

    user = relationship("User", backref="activities")
    pool = relationship("StockPool", backref="activities")


class NoteComment(Base):
    """分析结论点评（每用户可对笔记多次点评）。"""

    __tablename__ = "note_comments"

    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("analysis_notes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("(datetime('now','localtime'))"))

    note = relationship("AnalysisNote", back_populates="comments")
    user = relationship("User", backref="note_comments")
