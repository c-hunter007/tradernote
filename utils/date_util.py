"""日期工具。"""
from datetime import datetime


def format_date(dt: datetime | None) -> str:
    """格式化为 YYYY-MM-DD。"""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d")


def format_datetime(dt: datetime | None) -> str:
    """格式化为 YYYY-MM-DD HH:MM。"""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")
