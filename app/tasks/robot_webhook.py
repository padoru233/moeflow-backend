"""
异步通知对接的 QQ 机器人（webhook）。

创建项目/项目集不应该依赖机器人是否在线：真正的 HTTP 请求在这里通过 Celery
异步执行，不阻塞发起请求的用户操作；播报失败只在这里记录一条警告日志，不会
影响项目/项目集本身的创建结果。
"""

import requests
from celery.utils.log import get_task_logger

from app import celery

logger = get_task_logger(__name__)


@celery.task(name="tasks.notify_team_robot_task", time_limit=30)
def notify_team_robot_task(webhook_url, endpoint, payload, auth_token=None, timeout=15):
    """实际发起 webhook 请求，失败时只记录警告日志"""
    try:
        headers = {}
        if auth_token:
            headers["X-Auth-Token"] = auth_token
        url = webhook_url.rstrip("/")
        if url.endswith("/episode/complete"):
            url = url[: -len("/episode/complete")]
        response = requests.post(
            url + endpoint,
            json=payload,
            headers=headers or None,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        response = exc.response
        try:
            detail = response.json().get("detail")
        except (AttributeError, ValueError):
            detail = None
        logger.warning(
            "机器人播报失败：endpoint=%s payload=%s error=%s",
            endpoint,
            payload,
            detail or exc,
        )
    except Exception as exc:
        logger.warning(
            "机器人播报失败：endpoint=%s payload=%s error=%s",
            endpoint,
            payload,
            exc,
        )
