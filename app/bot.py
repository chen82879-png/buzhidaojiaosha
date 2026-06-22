from dataclasses import dataclass
from datetime import datetime, timedelta

from app.alert_rules import (
    FOLLOWUP_TIMEOUT_MINUTES,
    REPLY_TIMEOUT_MINUTES,
    SELF_REPLY_TIMEOUT_MINUTES,
    WAIT_TIMEOUT_MINUTES,
    is_followup_keyword,
    is_ignored_customer_text,
)
from app.fixed_keywords import FIXED_KEYWORDS
from app.matcher import match_enabled_keyword, match_message
from app.models import MonitorTask, PendingMessage
from app.staff_identity import StaffIdentity
from app.telegram_utils import build_message_url

@dataclass(frozen=True)
class NormalizedTelegramMessage:
    chat_id: str
    chat_name: str
    chat_username: str
    message_id: int
    sender_user_id: int
    sender_username: str
    text: str
    message_time: datetime
    reply_to_message_id: int | None
    sender_display_name: str = ""
    media_group_id: int | None = None
    message_kind: str = "text"


async def handle_incoming_message(
    message: NormalizedTelegramMessage,
    repo,
    queue,
    timeout_minutes: int,
    now_timestamp: float,
    staff_identity: StaffIdentity | None = None,
    keep_keywords: tuple[str, ...] = (),
    work_mode=None,
) -> None:
    rules = repo.list_enabled_rules()
    enabled_chat_ids = {rule.chat_id for rule in rules}
    if message.chat_id not in enabled_chat_ids:
        return
    keyword_configs = repo.list_keyword_configs() if hasattr(repo, "list_keyword_configs") else []
    identity = staff_identity or StaffIdentity.source_defaults()
    configured_staff_ids = {
        chat_id for config in keyword_configs if config.enabled for chat_id in config.recipient_chat_ids
    }
    is_configured_staff = identity.is_staff(
        message.sender_user_id,
        message.sender_display_name or message.sender_username,
    ) or message.sender_user_id in configured_staff_ids
    is_keep_command = is_followup_keyword(message.text, keep_keywords)
    if (
        message.media_group_id is not None
        and hasattr(repo, "has_media_group_snapshot")
        and repo.has_media_group_snapshot(message.chat_id, message.media_group_id)
    ):
        return
    if hasattr(repo, "upsert_message_snapshot"):
        repo.upsert_message_snapshot(
            chat_id=message.chat_id,
            message_id=message.message_id,
            sender_user_id=message.sender_user_id,
            sender_username=message.sender_username,
            is_staff=is_configured_staff,
            text=message.text,
            message_time=message.message_time,
            reply_to_message_id=message.reply_to_message_id,
            sender_display_name=message.sender_display_name,
            media_group_id=message.media_group_id,
            message_kind=message.message_kind,
        )
    if work_mode is not None and not work_mode.is_working:
        return

    match = match_message(message.chat_id, message.text, rules)
    keyword_config = match_enabled_keyword(message.text, keyword_configs)
    if match is not None:
        _record_keyword_hits(repo, message, match, keyword_configs)
    is_wait_command = (
        is_configured_staff
        and message.reply_to_message_id is not None
        and match is not None
        and keyword_config is not None
        and keyword_config.alert_enabled
    )
    transition_root_message_id = None

    if message.reply_to_message_id is not None:
        if is_configured_staff and hasattr(repo, "complete_tasks_referencing"):
            completed_tasks = repo.complete_tasks_referencing(
                message.chat_id,
                message.reply_to_message_id,
                message.message_time,
            )
            for task in completed_tasks:
                if hasattr(repo, "add_task_context_message"):
                    repo.add_task_context_message(task.id, message.message_id)
            for task in completed_tasks:
                await queue.close_pending(task.id)
            if completed_tasks:
                base_task = next(
                    (task for task in reversed(completed_tasks) if task.task_type in {"wait", "followup"}),
                    None,
                )
                if is_keep_command and base_task is not None:
                    await _create_followup_task(repo, queue, message, base_task)
                elif is_wait_command and base_task is not None:
                    transition_root_message_id = base_task.root_message_id
                else:
                    return
            elif is_keep_command and hasattr(repo, "latest_completed_wait_for_reference"):
                wait_task = repo.latest_completed_wait_for_reference(
                    message.chat_id, message.reply_to_message_id
                )
                if wait_task is not None:
                    await _create_followup_task(repo, queue, message, wait_task)
                return

    if not is_configured_staff:
        if is_ignored_customer_text(message.text):
            return
        if message.reply_to_message_id is not None and hasattr(repo, "get_message_snapshot"):
            replied_snapshot = repo.get_message_snapshot(message.chat_id, message.reply_to_message_id)
            if replied_snapshot is not None and replied_snapshot.is_staff:
                wait_task = (
                    repo.latest_wait_for_reference(message.chat_id, message.reply_to_message_id)
                    if hasattr(repo, "latest_wait_for_reference")
                    else None
                )
                if wait_task is not None:
                    await _create_reply_task(repo, queue, message, replied_snapshot, wait_task)
                return
            if (
                replied_snapshot is not None
                and replied_snapshot.sender_user_id == message.sender_user_id
            ):
                wait_task = (
                    repo.latest_wait_for_reference(message.chat_id, message.reply_to_message_id)
                    if hasattr(repo, "latest_wait_for_reference")
                    else None
                )
                if wait_task is not None:
                    await _create_self_reply_task(repo, queue, message, wait_task)
                return
        return

    if message.reply_to_message_id is None:
        return

    if keyword_config is None:
        return

    if not keyword_config.alert_enabled:
        return

    if match is None:
        return

    root_message_id = transition_root_message_id or message.reply_to_message_id or message.message_id
    url = build_message_url(message.chat_id, message.message_id, message.chat_username)
    if not hasattr(repo, "create_monitor_task"):
        return
    status = "pending"
    if hasattr(repo, "active_wait_for_reference") and repo.active_wait_for_reference(message.chat_id, root_message_id):
        status = "duplicate"
    recipient_chat_ids = keyword_config.recipient_chat_ids if keyword_config.alert_enabled else []
    task = repo.create_monitor_task(
        task_type="wait",
        rule_id=match.rule.id,
        chat_id=message.chat_id,
        chat_name=message.chat_name,
        keyword=keyword_config.keyword,
        staff_user_id=message.sender_user_id,
        staff_username=message.sender_username,
        root_message_id=root_message_id,
        wait_message_id=message.message_id,
        trigger_message_id=message.message_id,
        message_excerpt=message.text[:200],
        message_url=url,
        recipient_chat_ids=recipient_chat_ids,
        started_at=message.message_time,
        due_at=message.message_time + timedelta(minutes=WAIT_TIMEOUT_MINUTES),
        status=status,
    )
    if status == "duplicate":
        return
    if keyword_config.alert_enabled and recipient_chat_ids:
        await queue.add_pending(
            _pending_from_task(task, recipient_chat_ids),
            due_at=now_timestamp + WAIT_TIMEOUT_MINUTES * 60,
        )


async def _create_followup_task(repo, queue, message: NormalizedTelegramMessage, wait_task: MonitorTask) -> None:
    url = build_message_url(message.chat_id, message.message_id, message.chat_username)
    recipient_chat_ids = wait_task.recipient_chat_ids
    task = repo.create_monitor_task(
        task_type="followup",
        rule_id=wait_task.rule_id,
        chat_id=message.chat_id,
        chat_name=message.chat_name,
        keyword=wait_task.keyword,
        staff_user_id=wait_task.staff_user_id,
        staff_username=wait_task.staff_username,
        root_message_id=wait_task.root_message_id,
        wait_message_id=wait_task.wait_message_id,
        trigger_message_id=message.message_id,
        message_excerpt=message.text[:200],
        message_url=url,
        recipient_chat_ids=recipient_chat_ids,
        started_at=message.message_time,
        due_at=message.message_time + timedelta(minutes=FOLLOWUP_TIMEOUT_MINUTES),
    )
    await queue.add_pending(
        _pending_from_task(task, recipient_chat_ids),
        due_at=message.message_time.timestamp() + FOLLOWUP_TIMEOUT_MINUTES * 60,
    )


async def _create_reply_task(
    repo, queue, message: NormalizedTelegramMessage, replied_snapshot, wait_task: MonitorTask
) -> None:
    if not hasattr(repo, "create_monitor_task"):
        return
    config = next(
        (
            item for item in repo.list_keyword_configs()
            if item.keyword == wait_task.keyword and item.alert_enabled and item.recipient_chat_ids
        ),
        None,
    )
    if config is None:
        return
    if hasattr(repo, "add_task_context_message"):
        repo.add_task_context_message(wait_task.id, message.message_id)
    url = build_message_url(message.chat_id, message.message_id, message.chat_username)
    task = repo.create_monitor_task(
        task_type="reply",
        rule_id=wait_task.rule_id,
        chat_id=message.chat_id,
        chat_name=message.chat_name,
        keyword=wait_task.keyword,
        staff_user_id=message.sender_user_id,
        staff_username=message.sender_username,
        root_message_id=wait_task.root_message_id,
        wait_message_id=wait_task.wait_message_id,
        trigger_message_id=message.message_id,
        message_excerpt=message.text[:200],
        message_url=url,
        recipient_chat_ids=config.recipient_chat_ids,
        started_at=message.message_time,
        due_at=message.message_time + timedelta(minutes=REPLY_TIMEOUT_MINUTES),
    )
    await queue.add_pending(
        _pending_from_task(task, config.recipient_chat_ids),
        due_at=message.message_time.timestamp() + REPLY_TIMEOUT_MINUTES * 60,
    )


async def _create_self_reply_task(repo, queue, message: NormalizedTelegramMessage, base_task: MonitorTask) -> None:
    if hasattr(repo, "add_task_context_message"):
        repo.add_task_context_message(base_task.id, message.message_id)
    url = build_message_url(message.chat_id, message.message_id, message.chat_username)
    task = repo.create_monitor_task(
        task_type="self_reply",
        rule_id=base_task.rule_id,
        chat_id=message.chat_id,
        chat_name=message.chat_name,
        keyword=base_task.keyword,
        staff_user_id=message.sender_user_id,
        staff_username=message.sender_username,
        root_message_id=base_task.root_message_id,
        wait_message_id=base_task.wait_message_id,
        trigger_message_id=message.message_id,
        message_excerpt=message.text[:200],
        message_url=url,
        recipient_chat_ids=base_task.recipient_chat_ids,
        started_at=message.message_time,
        due_at=message.message_time + timedelta(minutes=SELF_REPLY_TIMEOUT_MINUTES),
    )
    await queue.add_pending(
        _pending_from_task(task, base_task.recipient_chat_ids),
        due_at=message.message_time.timestamp() + SELF_REPLY_TIMEOUT_MINUTES * 60,
    )


def _first_alert_config(repo):
    if not hasattr(repo, "list_keyword_configs"):
        return None
    for config in repo.list_keyword_configs():
        if config.enabled and config.alert_enabled and config.recipient_chat_ids:
            return config
    return None


def _first_rule_id(repo, chat_id: str) -> int:
    if not hasattr(repo, "list_enabled_rules"):
        return 0
    for rule in repo.list_enabled_rules():
        if rule.chat_id == chat_id:
            return rule.id
    return 0


def _pending_from_task(task: MonitorTask, recipient_chat_ids: list[int]) -> PendingMessage:
    timeout_message_id = task.trigger_message_id if task.task_type == "followup" else task.wait_message_id
    return PendingMessage(
        task_id=task.id,
        task_type=task.task_type,
        rule_id=task.rule_id,
        chat_id=task.chat_id,
        chat_name=task.chat_name,
        message_id=timeout_message_id,
        message_time=task.started_at,
        matched_keywords=[task.keyword],
        message_excerpt=task.message_excerpt,
        message_url=task.message_url,
        recipient_chat_ids=recipient_chat_ids,
        staff_user_id=task.staff_user_id,
        staff_username=task.staff_username,
    )


def _record_keyword_hits(repo, message: NormalizedTelegramMessage, match, configs) -> None:
    url = build_message_url(message.chat_id, message.message_id, message.chat_username)
    config_map = {config.keyword: config for config in configs}
    for keyword in match.matched_keywords:
        if keyword not in FIXED_KEYWORDS:
            continue
        config = config_map.get(keyword)
        if config is None or not config.stats_enabled:
            continue
        repo.record_keyword_hit(
            rule_id=match.rule.id,
            chat_id=message.chat_id,
            chat_name=message.chat_name,
            message_id=message.message_id,
            telegram_user_id=message.sender_user_id,
            telegram_username=message.sender_username,
            matched_keyword=keyword,
            message_excerpt=message.text[:200],
            message_url=url,
            message_time=message.message_time,
        )
