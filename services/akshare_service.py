"""akshare 封装：市场判断 + 名称查询 + 降级处理。

注意：本模块仅在新增加入股票时调用一次，名称缓存到 Stock 表后即复用。
"""
import re
from typing import Optional

import akshare as ak

# 6 位数字代码校验
_CODE_RE = re.compile(r"^\d{6}$")


def validate_code(code: str) -> bool:
    """校验是否为 6 位数字。"""
    if not code:
        return False
    return bool(_CODE_RE.match(code.strip()))


def detect_market(code: str) -> Optional[str]:
    """根据 6 位代码前缀判断市场。

    返回 SH / SZ / BJ；无效代码返回 None。

    规则：
      60xxxx / 68xxxx -> SH  (上交所主板 / 科创板)
      00xxxx / 30xxxx -> SZ  (深交所主板 / 创业板)
      43/83/87/92xxxx -> BJ  (北交所)
      其他 -> None
    """
    if not validate_code(code):
        return None
    code = code.strip()
    prefix2 = code[:2]
    prefix3 = code[:3]

    if prefix2 in ("60", "68"):
        return "SH"
    if prefix2 in ("00", "30"):
        return "SZ"
    if prefix3 in ("430", "830", "870", "920") or prefix2 in ("43", "83", "87", "92"):
        return "BJ"
    return None


def fetch_stock_name_from_akshare(code: str) -> Optional[str]:
    """通过 akshare 查询股票名称。

    - 调用 ak.stock_info_a_code_name() 获取沪深京 A 股列表（代码→名称映射）
    - 从缓存 DataFrame 中按 code 查找 name
    - 首次调用后结果被 @lru_cache 缓存，后续零网络开销
    - 任何异常均返回 None，不抛错
    """
    if not validate_code(code):
        return None
    code = code.strip()
    try:
        df = ak.stock_info_a_code_name()
        if df is None or df.empty:
            return None
        if "code" not in df.columns or "name" not in df.columns:
            return None
        row = df[df["code"] == code]
        if row.empty:
            return None
        name = row.iloc[0]["name"]
        if name is None:
            return None
        name = str(name).strip()
        return name if name else None
    except Exception:
        return None
