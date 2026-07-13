from dataclasses import dataclass
from datetime import datetime, timedelta

from app.fixed_keywords import FIXED_KEYWORDS
from app.ignore_words import is_continuing_staff_reply_text, is_ignored_followup_text
from app.matcher import match_enabled_keyword, match_message
from app.models import MonitorTask, PendingMessage
from app.telegram_utils import build_message_url

WAIT_TIMEOUT_MINUTES = 8
FOLLOWUP_TIMEOUT_MINUTES = 15
REPLY_TIMEOUT_MINUTES = 5
SELF_REPLY_TIMEOUT_MINUTES = 3


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


async def handle_incoming_message(
    message: NormalizedTelegramMessage,
    repo,
    queue,
    timeout_minutes: int,
    now_timestamp: float,
) -> None:
    rules = repo.list_enabled_rules()
    enabled_chat_ids = {rule.chat_id for rule in rules}
    if message.chat_id not in enabled_chat_ids:
        return
    keyword_configs = repo.list_keyword_configs() if hasattr(repo, "list_keyword_configs") else []
    configured_staff_ids = {
        chat_id for config in keyword_configs if config.enabled for chat_id in config.recipient_chat_ids
    }
    is_configured_staff = message.sender_user_id in configured_staff_ids
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
        )

    if message.reply_to_message_id is not None:
        if is_configured_staff and hasattr(repo, "complete_tasks_referencing"):
            if (
                is_continuing_staff_reply_text(message.text)
                and hasattr(repo, "pending_task_for_context")
            ):
                task = repo.pending_task_for_context(message.chat_id, message.reply_to_message_id)
                if task is not None and task.task_type == "followup":
                    if hasattr(repo, "add_task_context_message"):
                        repo.add_task_context_message(task.id, message.message_id)
                    return
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
                return
        elif hasattr(repo, "latest_completed_wait_for_reference"):
            if is_ignored_followup_text(message.text):
                return
            wait_task = repo.latest_completed_wait_for_reference(message.chat_id, message.reply_to_message_id)
            if wait_task is not None:
                await _create_followup_task(repo, queue, message, wait_task)
                return

    if not is_configured_staff:
        if message.reply_to_message_id is not None and hasattr(repo, "pending_task_for_context"):
            task = repo.pending_task_for_context(message.chat_id, message.reply_to_message_id)
            if task is not None and hasattr(repo, "add_task_context_message"):
                repo.add_task_context_message(task.id, message.message_id)
                return
        if message.reply_to_message_id is not None and hasattr(repo, "get_message_snapshot"):
            replied_snapshot = repo.get_message_snapshot(message.chat_id, message.reply_to_message_id)
            if replied_snapshot is not None and replied_snapshot.is_staff and not is_ignored_followup_text(message.text):
                await _create_reply_task(repo, queue, message, replied_snapshot)
                return
        if (
            message.reply_to_message_id is None
            and hasattr(repo, "latest_pending_task_for_customer")
            and not is_ignored_followup_text(message.text)
        ):
            active_task = repo.latest_pending_task_for_customer(message.chat_id, message.sender_user_id)
            if active_task is not None and active_task.task_type != "self_reply":
                await _create_self_reply_task(repo, queue, message, active_task)
                return
        match = match_message(message.chat_id, message.text, rules)
        if match is not None:
            _record_keyword_hits(repo, message, match)
        return

    match = match_message(message.chat_id, message.text, rules)
    if match is not None:
        _record_keyword_hits(repo, message, match)

    keyword_config = match_enabled_keyword(message.text, keyword_configs)
    if keyword_config is None:
        return

    if match is None:
        return

    root_message_id = message.reply_to_message_id or message.message_id
    url = build_message_url(message.chat_id, message.message_id, message.chat_username)
    if not hasattr(repo, "create_monitor_task"):
        return
    status = "pending"
    if hasattr(repo, "active_wait_for_reference") and repo.active_wait_for_reference(message.chat_id, root_message_id):
        status = "duplicate"
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
        recipient_chat_ids=keyword_config.recipient_chat_ids,
        started_at=message.message_time,
        due_at=message.message_time + timedelta(minutes=WAIT_TIMEOUT_MINUTES),
        status=status,
    )
    if status == "duplicate":
        return
    await queue.add_pending(
        _pending_from_task(task, keyword_config.recipient_chat_ids),
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


async def _create_reply_task(repo, queue, message: NormalizedTelegramMessage, replied_snapshot) -> None:
    if not hasattr(repo, "create_monitor_task"):
        return
    config = _first_alert_config(repo)
    if config is None:
        return
    url = build_message_url(message.chat_id, message.message_id, message.chat_username)
    task = repo.create_monitor_task(
        task_type="reply",
        rule_id=_first_rule_id(repo, message.chat_id),
        chat_id=message.chat_id,
        chat_name=message.chat_name,
        keyword=config.keyword,
        staff_user_id=message.sender_user_id,
        staff_username=message.sender_username,
        root_message_id=message.reply_to_message_id or message.message_id,
        wait_message_id=message.reply_to_message_id or message.message_id,
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


def _record_keyword_hits(repo, message: NormalizedTelegramMessage, match) -> None:
    url = build_message_url(message.chat_id, message.message_id, message.chat_username)
    for keyword in match.matched_keywords:
        if keyword not in FIXED_KEYWORDS:
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
