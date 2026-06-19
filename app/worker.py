import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from app.models import MonitorRule, MonitorTask, PendingMessage, RuleStaff
from app.redis_queue import RedisQueue

TASK_TIMEOUT_MINUTES = {
    "followup": 15,
    "reply": 5,
    "self_reply": 3,
}
SEVERE_ALERT_DELAY_MINUTES = 10


class TimeoutWorker:
    def __init__(
        self,
        queue: RedisQueue,
        alert_sender,
        rules_provider: Callable[[], list[MonitorRule]],
        task_repository=None,
        timeout_minutes: int = 15,
        send_timeout_seconds: float = 30,
    ):
        self.queue = queue
        self.alert_sender = alert_sender
        self.rules_provider = rules_provider
        self.task_repository = task_repository
        self.timeout_minutes = timeout_minutes
        self.send_timeout_seconds = send_timeout_seconds

    async def run_once(self, now_timestamp: float) -> None:
        members = await self.queue.due_members(now_timestamp)
        rules = {rule.id: rule for rule in self.rules_provider()}
        pending_by_member: dict[str, PendingMessage] = {}
        for member in members:
            try:
                task_id = int(member)
            except ValueError:
                await self.queue.remove_member(member)
                continue
            pending = await self.queue.get_pending(task_id)
            if pending is None or pending.status != "pending":
                await self.queue.remove_member(member)
                continue
            if not self._task_is_still_pending(task_id):
                await self.queue.close_pending(task_id)
                continue
            pending_by_member[member] = pending

        if self.task_repository is not None and hasattr(self.task_repository, "list_due_pending_tasks"):
            now = datetime.fromtimestamp(now_timestamp, tz=timezone.utc)
            for task in self.task_repository.list_due_pending_tasks(now):
                member = self.queue.member(task.id)
                if member not in pending_by_member:
                    pending_by_member[member] = self._pending_from_task(task)

        for member, pending in pending_by_member.items():
            task_id = pending.task_id
            alerted_at = datetime.fromtimestamp(now_timestamp, tz=timezone.utc)
            if not await self.queue.mark_alerted(task_id):
                if self.task_repository is not None:
                    self.task_repository.mark_task_alerted(task_id, alerted_at)
                    await self._schedule_severe(task_id, alerted_at)
                await self.queue.remove_member(member)
                continue
            if self.task_repository is not None:
                self.task_repository.mark_task_alerted(task_id, alerted_at)
            rule = rules.get(pending.rule_id)
            if rule is None:
                await self.queue.remove_member(member)
                continue
            if pending.recipient_chat_ids:
                staff_list = [
                    self._recipient_staff(pending, chat_id)
                    for chat_id in pending.recipient_chat_ids
                ]
            else:
                staff_list = [staff for staff in rule.staff if staff.enabled]
            delivered = False
            for staff in staff_list:
                if staff.enabled:
                    try:
                        result = await asyncio.wait_for(
                            self.alert_sender.send_timeout_alert(
                                staff,
                                pending,
                                TASK_TIMEOUT_MINUTES.get(pending.task_type, self.timeout_minutes),
                            ),
                            timeout=self.send_timeout_seconds,
                        )
                        delivered = delivered or result.get("status") == "sent"
                    except TimeoutError:
                        pass
            if delivered:
                await self._schedule_severe(task_id, alerted_at)
            await self.queue.remove_member(member)

        await self._run_severe_alerts(now_timestamp, rules)

    async def _schedule_severe(self, task_id: int, alerted_at: datetime) -> None:
        if self.task_repository is None or not hasattr(
            self.task_repository, "mark_first_alert_sent"
        ):
            return
        severe_due_at = alerted_at + timedelta(minutes=SEVERE_ALERT_DELAY_MINUTES)
        self.task_repository.mark_first_alert_sent(task_id, alerted_at, severe_due_at)
        await self.queue.add_severe(task_id, severe_due_at.timestamp())

    async def _run_severe_alerts(
        self,
        now_timestamp: float,
        rules: dict[int, MonitorRule],
    ) -> None:
        if self.task_repository is None or not hasattr(
            self.task_repository, "list_due_severe_tasks"
        ):
            return
        now = datetime.fromtimestamp(now_timestamp, tz=timezone.utc)
        tasks_by_id: dict[int, MonitorTask] = {
            task.id: task for task in self.task_repository.list_due_severe_tasks(now)
        }
        for member in await self.queue.due_severe_members(now_timestamp):
            try:
                task_id = int(member)
                task = self.task_repository.get_monitor_task(task_id)
            except (ValueError, KeyError):
                await self.queue.remove_severe_member(member)
                continue
            if task.status == "alerted" and task.severe_alert_sent_at is None:
                tasks_by_id[task_id] = task
            else:
                await self.queue.remove_severe_member(member)

        for task_id, task in tasks_by_id.items():
            member = self.queue.member(task_id)
            if not await self.queue.mark_severe_alerted(task_id):
                await self.queue.remove_severe_member(member)
                continue
            rule = rules.get(task.rule_id)
            if rule is None:
                await self.queue.remove_severe_member(member)
                continue
            pending = self._pending_from_task(task)
            staff_list = (
                [self._recipient_staff(pending, chat_id) for chat_id in pending.recipient_chat_ids]
                if pending.recipient_chat_ids
                else [staff for staff in rule.staff if staff.enabled]
            )
            delivered = False
            for staff in staff_list:
                if not staff.enabled:
                    continue
                try:
                    result = await asyncio.wait_for(
                        self.alert_sender.send_severe_timeout_alert(
                            staff,
                            pending,
                            SEVERE_ALERT_DELAY_MINUTES,
                        ),
                        timeout=self.send_timeout_seconds,
                    )
                    delivered = delivered or result.get("status") == "sent"
                except TimeoutError:
                    pass
            if delivered and hasattr(self.task_repository, "mark_severe_alert_sent"):
                self.task_repository.mark_severe_alert_sent(task_id, now)
            await self.queue.remove_severe_member(member)

    def _task_is_still_pending(self, task_id: int) -> bool:
        if self.task_repository is None or not hasattr(self.task_repository, "get_monitor_task"):
            return True
        try:
            return self.task_repository.get_monitor_task(task_id).status == "pending"
        except KeyError:
            return False

    def _pending_from_task(self, task: MonitorTask) -> PendingMessage:
        message_id = task.trigger_message_id if task.task_type == "followup" else task.wait_message_id
        return PendingMessage(
            task_id=task.id,
            task_type=task.task_type,
            rule_id=task.rule_id,
            chat_id=task.chat_id,
            chat_name=task.chat_name,
            message_id=message_id,
            message_time=task.started_at,
            matched_keywords=[task.keyword],
            message_excerpt=task.message_excerpt,
            message_url=task.message_url,
            recipient_chat_ids=task.recipient_chat_ids,
            staff_user_id=task.staff_user_id,
            staff_username=task.staff_username,
            status=task.status,
        )

    def _recipient_staff(self, pending: PendingMessage, chat_id: int) -> RuleStaff:
        fallback_username = pending.staff_username if chat_id == pending.staff_user_id else ""
        display = {"display_name": fallback_username or str(chat_id), "telegram_username": fallback_username}
        if self.task_repository is not None and hasattr(self.task_repository, "recipient_display_for_user"):
            display = self.task_repository.recipient_display_for_user(chat_id, fallback_username=fallback_username)
        return RuleStaff(
            id=0,
            rule_id=pending.rule_id,
            telegram_user_id=chat_id,
            telegram_username=display.get("telegram_username", ""),
            display_name=display.get("display_name", "") or display.get("telegram_username", "") or str(chat_id),
            enabled=True,
        )
