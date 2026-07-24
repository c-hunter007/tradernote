"""UI 工具：卡片样式、空状态、消息提示等通用组件。"""
import html

import streamlit as st

# 状态色板
COLOR_KEY_FOCUS = "#fde68a"  # 金色背景（重点关注）
COLOR_KEY_FOCUS_TEXT = "#b91c1c"  # 红色加粗
COLOR_REMOVED = "#e5e7eb"  # 灰色（已移出）


def _esc(text: str | None) -> str:
    """HTML 转义，避免用户内容注入。"""
    if text is None:
        return ""
    return html.escape(str(text))


def render_card(title: str, body: str | None = None, color: str = "var(--secondary-background-color)") -> None:
    """渲染一个简单的卡片块（仅用于展示）。"""
    if body is None:
        body = ""
    st.markdown(
        f"""
        <div style="background-color: {color}; border: 1px solid var(--border-color); border-radius: 8px;
                    padding: 12px 16px; margin-bottom: 8px;">
            <div style="font-weight: 600; font-size: 16px; color: var(--text-color);">{_esc(title)}</div>
            <div style="font-size: 13px; color: var(--text-color); opacity: 0.7;">{_esc(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(message: str, icon: str = "📭") -> None:
    """渲染空状态。"""
    st.markdown(
        f"""
        <div style="text-align:center; padding: 40px 16px; color: var(--text-color); opacity: 0.5;">
            <div style="font-size: 36px;">{_esc(icon)}</div>
            <div style="font-size: 14px; margin-top: 8px;">{_esc(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_key_focus_card(title: str, body: str = "") -> None:
    """渲染重点关注的股票卡片（金色背景 + 红色加粗）。"""
    st.markdown(
        f"""
        <div style="background-color: {COLOR_KEY_FOCUS}; border: 2px solid #f59e0b;
                    border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;">
            <div style="font-weight: 700; color: {COLOR_KEY_FOCUS_TEXT}; font-size: 16px;">
                ⭐ {_esc(title)}
            </div>
            <div style="font-size: 13px; color: #7c2d12;">{_esc(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_removed_card(title: str, body: str = "") -> None:
    """渲染已移出股票的卡片（灰色 + 斜体）。body 允许包含受控 HTML（如 <br/>）。"""
    st.markdown(
        f"""
        <div style="background-color: {COLOR_REMOVED}; border: 1px dashed #9ca3af;
                    border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;">
            <div style="font-weight: 500; color: #4b5563; font-style: italic; font-size: 16px;">
                ♻️ {_esc(title)}
            </div>
            <div style="font-size: 13px; color: #6b7280;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stock_card(
    code: str,
    name: str,
    market: str,
    added_date: str,
    added_by_username: str,
    initial_analysis: str | None,
    note_count: int,
    is_key_focus: bool = False,
) -> None:
    """渲染池内股票卡片。

    - is_key_focus=True：金色背景 + 红色加粗 + ⭐ 标记
    - is_key_focus=False：普通卡片
    """
    if is_key_focus:
        bg = COLOR_KEY_FOCUS
        border = "2px solid #f59e0b"
        title_color = COLOR_KEY_FOCUS_TEXT
        title_weight = 700
        star = "⭐ "
    else:
        bg = "var(--secondary-background-color)"
        border = "1px solid var(--border-color)"
        title_color = "var(--text-color)"
        title_weight = 600
        star = ""

    body_parts = [
        f"加入者：{_esc(added_by_username)}",
        f"加入于 {_esc(added_date)}",
        f"分析结论：{note_count} 条",
    ]
    body = " · ".join(body_parts)
    if initial_analysis:
        body += f"<br/><span style='color:var(--text-color);opacity:0.5;'>初始分析：{_esc(initial_analysis)}</span>"

    st.markdown(
        f"""
        <div style="background-color: {bg}; border: {border}; border-radius: 8px;
                    padding: 12px 16px; margin-bottom: 4px;">
            <div style="font-weight: {title_weight}; color: {title_color}; font-size: 16px;">
                {star}{_esc(code)} {_esc(name)} · {_esc(market)}
            </div>
            <div style="font-size: 13px; color: var(--text-color); opacity: 0.7;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_note_card(
    username: str,
    created_at: str,
    content: str,
    image_count: int = 0,
) -> None:
    """渲染分析结论卡片（与股票卡片风格对齐）。"""
    meta_parts = [f"**{_esc(username)}** · {_esc(created_at)}"]
    if image_count:
        meta_parts.append(f"🖼 {image_count} 张配图")
    meta = " · ".join(meta_parts)

    st.markdown(
        f"""
        <div style="background-color: var(--secondary-background-color); border: 1px solid var(--border-color); border-radius: 8px;
                    padding: 12px 16px; margin-bottom: 4px;">
            <div style="font-size: 13px; color: var(--text-color); opacity: 0.7; margin-bottom: 6px;">{meta}</div>
            <div style="font-size: 14px; color: var(--text-color); white-space: pre-wrap;">{_esc(content)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
