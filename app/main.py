import asyncio
import contextlib
import logging
import os
import time
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from redis import asyncio as redis_async

from app.bot import FOLLOWUP_TIMEOUT_MINUTES, WAIT_TIMEOUT_MINUTES, NormalizedTelegramMessage, handle_incoming_message
from app.config import Settings, load_settings
from app.db import connect, migrate
from app.alerts import TelegramAlertSender
from app.fixed_keywords import FIXED_KEYWORDS
from app.monitor_groups import DEFAULT_MONITOR_GROUP_NAMES
from app.models import KeywordConfig
from app.redis_queue import RedisQueue
from app.repositories import Repository
from app.session_bootstrap import restore_session_from_env
from app.worker import TimeoutWorker


templates = Jinja2Templates(directory="app/templates")
DISPLAY_TZ = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)


def build_repository(settings: Settings) -> Repository:
    conn = connect(settings.sqlite_path)
    migrate(conn)
    return Repository(conn)


def build_queue(settings: Settings) -> RedisQueue:
    return RedisQueue(redis_async.from_url(settings.redis_url, decode_responses=True))


def normalize_telegram_update(payload: dict) -> NormalizedTelegramMessage | None:
    raw_message = payload.get("message") or payload.get("channel_post")
    if not raw_message:
        return None
    chat = raw_message.get("chat") or {}
    sender = raw_message.get("from") or {}
    reply = raw_message.get("reply_to_message") or {}
    text = raw_message.get("text") or raw_message.get("caption") or ""
    if not text:
        return None
    return NormalizedTelegramMessage(
        chat_id=str(chat.get("id", "")),
        chat_name=chat.get("title") or chat.get("first_name") or str(chat.get("id", "")),
        chat_username=chat.get("username") or "",
        message_id=int(raw_message["message_id"]),
        sender_user_id=int(sender.get("id", 0)),
        sender_username=sender.get("username") or "",
        text=text,
        message_time=datetime.fromtimestamp(int(raw_message.get("date", time.time())), tz=timezone.utc),
        reply_to_message_id=reply.get("message_id"),
    )


def as_local_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(DISPLAY_TZ)


def format_local_datetime(value) -> str:
    local_value = as_local_datetime(value)
    if local_value is None:
        return ""
    return local_value.strftime("%Y-%m-%d %H:%M:%S")


def build_task_view(task, now: datetime) -> dict[str, object]:
    due_at = task.due_at
    if isinstance(due_at, str):
        due_at = datetime.fromisoformat(due_at)
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    remaining_minutes = max(0, ceil((due_at - now).total_seconds() / 60))
    first_alert_sent_at = getattr(task, "first_alert_sent_at", None)
    severe_due_at = getattr(task, "severe_due_at", None)
    severe_alert_sent_at = getattr(task, "severe_alert_sent_at", None)
    return {
        "id": getattr(task, "id", None),
        "status": getattr(task, "status", ""),
        "task_type": task.task_type,
        "keyword": task.keyword,
        "chat_name": task.chat_name,
        "chat_id": task.chat_id,
        "message_excerpt": task.message_excerpt,
        "message_url": task.message_url,
        "remaining_label": "已到期" if remaining_minutes == 0 else f"剩余 {remaining_minutes} 分钟",
        "due_label": as_local_datetime(due_at).strftime("%H:%M") if as_local_datetime(due_at) else "",
        "due_timestamp": int(due_at.timestamp()),
        "first_alert_label": format_local_datetime(first_alert_sent_at),
        "severe_due_label": format_local_datetime(severe_due_at),
        "severe_due_time_label": (
            as_local_datetime(severe_due_at).strftime("%H:%M")
            if as_local_datetime(severe_due_at)
            else ""
        ),
        "severe_alert_label": format_local_datetime(severe_alert_sent_at),
    }


def summarize_status(repo, settings: Settings) -> dict[str, object]:
    open_tasks = repo.list_open_tasks() if hasattr(repo, "list_open_tasks") else []
    keyword_configs = repo.list_keyword_configs() if hasattr(repo, "list_keyword_configs") else []
    return {
        "service": "running",
        "webhook_configured": bool(settings.webhook_url),
        "listener_configured": bool(settings.telegram_api_id and settings.telegram_api_hash and settings.listener_phone),
        "redis_configured": bool(settings.redis_url),
        "sqlite_path": settings.sqlite_path,
        "open_task_count": len(open_tasks),
        "keyword_count": len(keyword_configs),
    }


def build_mini_tasks(repo, now: datetime) -> list[dict[str, object]]:
    tasks = repo.list_open_tasks() if hasattr(repo, "list_open_tasks") else []
    return [
        build_task_view(task, now)
        for task in tasks
        if getattr(task, "task_type", "") in {"wait", "followup", "reply", "self_reply"}
    ]


def build_mini_task_groups(repo, now: datetime) -> dict[str, list[dict[str, object]]]:
    groups = {"wait": [], "followup": [], "reply": [], "self_reply": []}
    for task in build_mini_tasks(repo, now):
        task_type = str(task.get("task_type", ""))
        if task_type in groups:
            groups[task_type].append(task)
    return groups


def build_mini_keyword_rows(repo) -> list[dict[str, object]]:
    hit_counts = repo.keyword_hit_counts() if hasattr(repo, "keyword_hit_counts") else []
    hit_count_map = {str(row["matched_keyword"]): row["count"] for row in hit_counts}
    config_map = {}
    if hasattr(repo, "list_keyword_configs"):
        config_map = {config.keyword: config for config in repo.list_keyword_configs()}
    return [
        {
            "text": keyword,
            "hit_count": hit_count_map.get(keyword, 0),
            "enabled": config_map.get(keyword).enabled if keyword in config_map else False,
            "stats_enabled": config_map.get(keyword).stats_enabled if keyword in config_map else False,
            "task_enabled": config_map.get(keyword).task_enabled if keyword in config_map else False,
            "alert_enabled": config_map.get(keyword).alert_enabled if keyword in config_map else True,
            "recipient_chat_ids": ", ".join(
                str(chat_id) for chat_id in config_map.get(keyword).recipient_chat_ids
            ) if keyword in config_map else "",
        }
        for keyword in FIXED_KEYWORDS
    ]


def build_mini_stats(repo, now: datetime) -> dict[str, object]:
    rows = repo.keyword_statistics(now=now) if hasattr(repo, "keyword_statistics") else []
    keyword_rows = []
    for row in rows:
        keyword_rows.append(
            {
                **row,
                "latest_label": format_local_datetime(row.get("latest_time")),
            }
        )
    open_tasks = repo.list_open_tasks() if hasattr(repo, "list_open_tasks") else []
    audit_records = repo.recent_audit_records(limit=5) if hasattr(repo, "recent_audit_records") else []
    history_check = repo.history_check_summary(limit=5, now=now) if hasattr(repo, "history_check_summary") else {}
    return {
        "today_count": sum(int(row.get("today_count") or 0) for row in keyword_rows),
        "seven_day_count": sum(int(row.get("seven_day_count") or 0) for row in keyword_rows),
        "total_count": sum(int(row.get("total_count") or 0) for row in keyword_rows),
        "enabled_count": sum(1 for row in keyword_rows if row.get("enabled")),
        "open_task_count": sum(
            1
            for task in open_tasks
            if getattr(task, "task_type", "") in {"wait", "followup", "reply", "self_reply"}
        ),
        "keywords": keyword_rows,
        "audit_records": audit_records,
        "history_check": history_check,
    }


def create_app(
    repo=None,
    queue=None,
    settings: Settings | None = None,
    message_handler=handle_incoming_message,
    now_provider=None,
) -> FastAPI:
    settings = settings or load_settings()
    telethon_session_path = getattr(settings, "telethon_session_path", "")
    if telethon_session_path:
        restore_session_from_env(telethon_session_path, os.getenv("TELETHON_SESSION_B64", ""))
    repo = repo or build_repository(settings)
    queue = queue or build_queue(settings)
    now_provider = now_provider or (lambda: datetime.now(timezone.utc))
    app = FastAPI(title="Telegram Alert Bot")
    app.state.timeout_worker_enabled = bool(settings.telegram_bot_token)
    app.state.listener_enabled = bool(
        getattr(settings, "telegram_api_id", 0)
        and getattr(settings, "telegram_api_hash", "")
        and getattr(settings, "listener_phone", "")
        and telethon_session_path
        and Path(telethon_session_path).exists()
    )
    app.state.timeout_worker_task = None
    app.state.listener_task = None
    app.state.maintenance_task = None
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    async def timeout_worker_loop() -> None:
        bot = Bot(token=settings.telegram_bot_token)
        worker = TimeoutWorker(
            queue=queue,
            alert_sender=TelegramAlertSender(bot),
            rules_provider=repo.list_enabled_rules,
            task_repository=repo,
            timeout_minutes=WAIT_TIMEOUT_MINUTES,
        )
        try:
            while True:
                try:
                    await worker.run_once(time.time())
                except Exception:
                    logger.exception("timeout worker iteration failed")
                await asyncio.sleep(5)
        finally:
            await bot.session.close()

    async def maintenance_loop() -> None:
        while True:
            now = datetime.now(timezone.utc)
            repo.rollup_keyword_hits(before=now)
            repo.cleanup_old_details(now=now, detail_retention_days=3, rollup_retention_days=30)
            await asyncio.sleep(3600)

    async def listener_loop() -> None:
        from app.listener import run_listener

        try:
            await run_listener(settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("telegram listener stopped unexpectedly")

    @app.on_event("startup")
    async def start_timeout_worker() -> None:
        if app.state.timeout_worker_enabled:
            app.state.timeout_worker_task = asyncio.create_task(timeout_worker_loop())
        if app.state.listener_enabled:
            app.state.listener_task = asyncio.create_task(listener_loop())
        if hasattr(repo, "rollup_keyword_hits") and hasattr(repo, "cleanup_old_details"):
            app.state.maintenance_task = asyncio.create_task(maintenance_loop())

    @app.on_event("shutdown")
    async def stop_timeout_worker() -> None:
        task = app.state.timeout_worker_task
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        maintenance_task = app.state.maintenance_task
        if maintenance_task is not None:
            maintenance_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await maintenance_task
        listener_task = app.state.listener_task
        if listener_task is not None:
            listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener_task

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return RedirectResponse("/mini/tasks")

    @app.get("/admin", response_class=HTMLResponse)
    async def legacy_admin():
        return RedirectResponse("/mini/tasks")

    @app.get("/admin/rules", response_class=HTMLResponse)
    async def legacy_admin_rules():
        return RedirectResponse("/mini/keywords")

    @app.get("/admin/alerts", response_class=HTMLResponse)
    async def legacy_admin_alerts():
        return RedirectResponse("/mini/stats")

    @app.get("/admin/keywords", response_class=HTMLResponse)
    async def admin_keywords(request: Request):
        return RedirectResponse("/mini/keywords")

    @app.get("/mini", response_class=HTMLResponse)
    async def mini_home():
        return RedirectResponse("/mini/tasks")

    @app.get("/mini/tasks", response_class=HTMLResponse)
    async def mini_tasks(request: Request):
        now = now_provider()
        task_groups = build_mini_task_groups(repo, now)
        return templates.TemplateResponse(
            request,
            "mini_tasks.html",
            {
                "title": "任务",
                "active_tab": "tasks",
                "task_groups": task_groups,
                "task_count": sum(len(group) for group in task_groups.values()),
            },
        )

    @app.get("/mini/keywords", response_class=HTMLResponse)
    async def mini_keywords(request: Request):
        return templates.TemplateResponse(
            request,
            "mini_keywords.html",
            {
                "title": "关键词",
                "active_tab": "keywords",
                "keywords": build_mini_keyword_rows(repo),
            },
        )

    @app.get("/mini/stats", response_class=HTMLResponse)
    async def mini_stats(request: Request):
        now = now_provider()
        return templates.TemplateResponse(
            request,
            "mini_stats.html",
            {
                "title": "统计",
                "active_tab": "stats",
                "stats": build_mini_stats(repo, now),
            },
        )

    @app.get("/mini/history", response_class=HTMLResponse)
    async def mini_history(request: Request):
        now = now_provider()
        history = repo.history_check_summary(limit=20, now=now) if hasattr(repo, "history_check_summary") else {}
        return templates.TemplateResponse(
            request,
            "mini_history.html",
            {
                "title": "历史检测",
                "active_tab": "history",
                "history": history,
            },
        )

    @app.post("/mini/keywords")
    async def save_mini_keywords(request: Request):
        form = await request.form()
        configs: list[KeywordConfig] = []
        for keyword in FIXED_KEYWORDS:
            raw_ids = str(form.get(f"chat_ids::{keyword}", ""))
            chat_ids: list[int] = []
            for part in raw_ids.replace("，", ",").split(","):
                value = part.strip()
                if value:
                    chat_ids.append(int(value))
            stats_enabled = form.get(f"stats_enabled::{keyword}") == "1"
            alert_enabled = form.get(f"alert_enabled::{keyword}") == "1"
            task_enabled = form.get(f"task_enabled::{keyword}") == "1" or alert_enabled
            configs.append(
                KeywordConfig(
                    keyword=keyword,
                    enabled=stats_enabled or task_enabled,
                    stats_enabled=stats_enabled,
                    task_enabled=task_enabled,
                    alert_enabled=alert_enabled,
                    recipient_chat_ids=chat_ids,
                )
            )
        repo.save_keyword_configs(configs)
        return RedirectResponse("/mini/keywords", status_code=303)

    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request):
        payload = await request.json()
        message = normalize_telegram_update(payload)
        if message is not None:
            await message_handler(message, repo, queue, settings.global_timeout_minutes, time.time())
        return {"ok": True}

    @app.get("/api/audit/recent")
    async def api_audit_recent():
        records = repo.recent_audit_records(limit=50) if hasattr(repo, "recent_audit_records") else []
        return {"records": records}

    @app.get("/api/wait/pending")
    async def api_wait_pending():
        now = now_provider()
        tasks = repo.list_open_tasks() if hasattr(repo, "list_open_tasks") else []
        return {"tasks": [build_task_view(task, now) for task in tasks if task.task_type == "wait"]}

    @app.get("/api/tasks/open")
    async def api_tasks_open():
        now = now_provider()
        return {"groups": build_mini_task_groups(repo, now)}

    @app.get("/api/history/check")
    async def api_history_check():
        summary = repo.history_check_summary(limit=20, now=now_provider()) if hasattr(repo, "history_check_summary") else {}
        return {"summary": summary}

    @app.get("/api/config/status")
    async def api_config_status():
        status = summarize_status(repo, settings)
        listener_session_exists = bool(telethon_session_path and Path(telethon_session_path).exists())
        enabled_chats = repo.list_enabled_chat_summaries() if hasattr(repo, "list_enabled_chat_summaries") else []
        enabled_chat_count = repo.enabled_chat_count() if hasattr(repo, "enabled_chat_count") else len(enabled_chats)
        return {
            "service": status["service"],
            "webhook_configured": status["webhook_configured"],
            "redis_configured": status["redis_configured"],
            "listener_env_configured": status["listener_configured"],
            "listener_session_exists": listener_session_exists,
            "listener_enabled": bool(app.state.listener_enabled),
            "target_group_count": len(DEFAULT_MONITOR_GROUP_NAMES),
            "target_group_names": DEFAULT_MONITOR_GROUP_NAMES,
            "enabled_chat_count": enabled_chat_count,
            "enabled_chats": enabled_chats,
            "keyword_count": status["keyword_count"],
            "open_task_count": status["open_task_count"],
        }

    @app.post("/api/config/configure-groups")
    async def api_configure_groups():
        from telethon import TelegramClient

        from app.group_configurator import configure_monitor_groups_from_dialogs

        if not app.state.listener_enabled:
            return {
                "ok": False,
                "error": "listener is not enabled or session is missing",
            }
        client = TelegramClient(
            settings.telethon_session_path,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        await client.start(phone=settings.listener_phone)
        try:
            result = await configure_monitor_groups_from_dialogs(repo, client)
        finally:
            await client.disconnect()
        return {"ok": True, **result}

    return app


app = create_app()
