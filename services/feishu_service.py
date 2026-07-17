"""飞书自定义机器人消息推送（消息卡片格式）。"""
import json
import logging
import threading
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

ACTION_CONFIG: dict[str, tuple[str, str]] = {
    "add_stock":      ("📥 新增股票",     "green"),
    "remove_stock":   ("📤 移出股票",     "red"),
    "set_focus":      ("⭐ 设置重点关注",  "orange"),
    "unset_focus":    ("💫 取消重点关注",  "grey"),
    "write_note":     ("📝 新增分析",     "blue"),
    "edit_note":      ("✏️ 编辑分析",     "wathet"),
    "delete_note":    ("🗑️ 删除分析",     "purple"),
    "comment":        ("💬 点评",         "indigo"),
}

_TIMEOUT = (5, 10)


def _build_card(action: str, pool_name: str, username: str, description: str) -> dict:
    action_title, template = ACTION_CONFIG.get(action, ("🔄 操作", "blue"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return {
        "schema": "2.0",
        "header": {
            "title": {"tag": "plain_text", "content": f"📊 TradeNote · {pool_name}"},
            "template": template,
        },
        "body": {
            "direction": "vertical",
            "elements": [
                {"tag": "markdown", "content": f"**{action_title}**"},
                {"tag": "hr"},
                {"tag": "markdown", "content": f"👤 **用户**：{username}"},
                {"tag": "markdown", "content": f"📝 **内容**：{description}"},
                {"tag": "markdown", "content": f"🕐 {now}"},
            ],
        },
    }


def send_feishu_notification(
    webhook_url: str,
    action: str,
    pool_name: str,
    username: str,
    description: str,
) -> None:
    """同步发送飞书消息卡片。"""
    card = _build_card(action, pool_name, username, description)
    payload = {
        "msg_type": "interactive",
        "card": card,
    }
    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            timeout=_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.warning("飞书推送失败: %s", data.get("msg"))
    except requests.RequestException as e:
        logger.error("飞书推送网络异常: %s", e)


def send_feishu_notification_async(
    webhook_url: str,
    action: str,
    pool_name: str,
    username: str,
    description: str,
) -> None:
    """异步发送飞书通知（daemon 线程，不阻塞主流程）。"""
    threading.Thread(
        target=send_feishu_notification,
        args=(webhook_url, action, pool_name, username, description),
        daemon=True,
    ).start()
