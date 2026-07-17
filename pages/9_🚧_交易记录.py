"""交易记录及分析（后期开发，当前占位）。"""
import streamlit as st

from utils.page import render_page_header, render_sidebar_user
from utils.ui import render_empty_state

render_page_header("交易记录", "🚧", "后期再开发")
render_sidebar_user()

render_empty_state(
    "本模块为后期开发占位，当前版本暂不实现交易记录及分析功能。",
    icon="🚧",
)
