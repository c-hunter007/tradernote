"""会话管理：基于 st.session_state + streamlit-cookies-manager。"""
from datetime import datetime, timedelta

import streamlit as st
from streamlit_cookies_manager import CookieManager

from config import SESSION_DAYS

# cookie 中保存的用户 ID 字段
COOKIE_USER_ID = "tn_uid"
COOKIE_USERNAME = "tn_user"
COOKIE_ROLE = "tn_role"


def get_cookie_manager() -> CookieManager:
    """获取 CookieManager 实例（session 内缓存，未就绪时重建）。

    不能用 @st.cache_resource（跨 run 缓存会导致组件不再重新调用、cookie 不同步），
    也不能每次都 new（同 run 多次实例化会触发 StreamlitDuplicateElementKey）。
    用 st.session_state 在单次 script run 内缓存实例；若未就绪则重建以重新同步 cookie。

    CookieManager 默认 cookie 过期 365 天，库未提供公开 API 修改；
    此处通过覆盖 _default_expiry 实现 30 天（SESSION_DAYS）过期。
    """
    cm = st.session_state.get("_cookie_manager")
    if cm is not None and cm.ready():
        return cm
    cm = CookieManager()
    cm._default_expiry = datetime.now() + timedelta(days=SESSION_DAYS)
    st.session_state["_cookie_manager"] = cm
    return cm


def init_cookies() -> CookieManager:
    """初始化 cookie manager（在每个页面顶部调用一次）。"""
    cm = get_cookie_manager()
    if not cm.ready():
        st.stop()
    return cm


def login_user(user_id: int, username: str, role: str, remember: bool = True) -> None:
    """登录成功后写入 session_state，cookie 延迟到下一个稳定 run 写入。"""
    st.session_state["user_id"] = user_id
    st.session_state["username"] = username
    st.session_state["role"] = role

    if remember:
        st.session_state["_pending_cookies"] = (
            "set",
            [(COOKIE_USER_ID, str(user_id)), (COOKIE_USERNAME, username), (COOKIE_ROLE, role)],
        )


def flush_pending_cookies() -> None:
    """处理延迟的 cookie 写入（在 app.py 的稳定 run 中调用）。"""
    pending = st.session_state.pop("_pending_cookies", None)
    if pending is None:
        return
    action, items = pending
    cm = get_cookie_manager()
    if cm._cookies is None:
        cm._cookies = {}
    if action == "set":
        expiry = (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat()
        for name, value in items:
            cm._queue[name] = dict(value=value, expires_at=expiry, path=cm._path)
    elif action == "clear":
        for name in items:
            cm._queue[name] = dict(value=None, path=cm._path)
    cm.save()


def logout_user() -> None:
    """登出：清除 session_state，cookie 延迟到下一个稳定 run 清除。"""
    for key in ("user_id", "username", "role"):
        st.session_state.pop(key, None)
    st.session_state["_pending_cookies"] = (
        "clear",
        [COOKIE_USER_ID, COOKIE_USERNAME, COOKIE_ROLE],
    )


def restore_from_cookie() -> bool:
    """尝试从 cookie 恢复登录态。返回是否成功恢复。"""
    if "user_id" in st.session_state:
        return True

    cm = get_cookie_manager()
    user_id = cm.get(COOKIE_USER_ID)
    username = cm.get(COOKIE_USERNAME)
    role = cm.get(COOKIE_ROLE)

    if user_id and username and role:
        st.session_state["user_id"] = int(user_id)
        st.session_state["username"] = username
        st.session_state["role"] = role
        return True
    return False


def is_logged_in() -> bool:
    return "user_id" in st.session_state


def is_admin() -> bool:
    return st.session_state.get("role") == "admin"


def current_user() -> dict | None:
    if not is_logged_in():
        return None
    return {
        "id": st.session_state["user_id"],
        "username": st.session_state["username"],
        "role": st.session_state["role"],
    }


def require_login() -> dict:
    """页面顶部调用，未登录则显示提示并停止。返回当前用户 dict。"""
    init_cookies()
    restore_from_cookie()
    if not is_logged_in():
        st.warning("请先登录。")
        st.switch_page("pages/0_📊_仪表盘.py")
        st.stop()
    return current_user()


def require_admin() -> dict:
    """页面顶部调用，非管理员则提示并停止。"""
    user = require_login()
    if not is_admin():
        st.error("仅管理员可访问此页面。")
        st.stop()
    return user
