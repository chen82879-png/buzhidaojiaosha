from datetime import datetime, timezone
import asyncio

from app.models import MonitorRule, MonitorTask, PendingMessage, RuleStaff
from app.redis_queue import RedisQueue
from app.worker import TimeoutWorker


class FakeAlertSender:
    def __init__(self):
        self.sent = []
        self.staff = []

    async def send_timeout_alert(self, staff, pending, timeout_minutes):
        self.sent.append((staff.telegram_user_id, pending.message_id, timeout_minutes))
        self.staff.append(staff)
        return {"status": "sent", "error_message": ""}


class HangingAlertSender:
    async def send_timeout_alert(self, staff, pending, timeout_minutes):
        await asyncio.sleep(60)


class FakeTaskRepository:
    def __init__(self):
        self.alerted = []
        self.due_tasks = []
        self.tasks = {}

    def mark_task_alerted(self, task_id, alerted_at):
        self.alerted.append((task_id, alerted_at))

    def list_due_pending_tasks(self, now):
        return self.due_tasks

    def get_monitor_task(self, task_id):
        return self.tasks[task_id]

    def recipient_display_for_user(self, telegram_user_id, fallback_username=""):
        if telegram_user_id == 9001:
            return {"display_name": "Y_YY_Stormrage", "telegram_username": fallback_username or "Y_YY_GRYBUGES"}
        return {"display_name": fallback_username or str(telegram_user_id), "telegram_username": fallback_username}


async def test_due_pending_message_sends_one_alert(fake_redis):
    queue = RedisQueue(fake_redis)
    staff = RuleStaff(
        id=1,
        rule_id=1,
        telegram_user_id=9001,
        telegram_username="ML_YYZB3",
        display_name="YY_6/9_值班号3",
        enabled=True,
    )
    rule = MonitorRule(id=1, chat_id="-1001", chat_name="Ops", enabled=True, staff=[staff])
    pending = PendingMessage(
        task_id=20,
        task_type="wait",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        message_id=50,
        message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        matched_keywords=["充值"],
        message_excerpt="充值失败",
        message_url="https://t.me/c/1001/50",
        recipient_chat_ids=[9001],
    )
    await queue.add_pending(pending, due_at=1000)
    sender = FakeAlertSender()
    worker = TimeoutWorker(queue=queue, alert_sender=sender, rules_provider=lambda: [rule], timeout_minutes=15)

    await worker.run_once(now_timestamp=1000)
    await worker.run_once(now_timestamp=1001)

    assert sender.sent == [(9001, 50, 15)]


async def test_already_alerted_redis_member_marks_task_alerted_and_leaves_list(fake_redis):
    queue = RedisQueue(fake_redis)
    pending = PendingMessage(
        task_id=20,
        task_type="wait",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        message_id=50,
        message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        matched_keywords=["充值"],
        message_excerpt="充值失败",
        message_url="https://t.me/c/1001/50",
        recipient_chat_ids=[9001],
    )
    await queue.add_pending(pending, due_at=1000)
    await queue.mark_alerted(20)
    repo = FakeTaskRepository()
    repo.tasks[20] = MonitorTask(
        id=20,
        task_type="wait",
        status="pending",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        keyword="充值",
        staff_user_id=9001,
        staff_username="ML_YYZB3",
        root_message_id=50,
        wait_message_id=50,
        trigger_message_id=50,
        message_excerpt="充值失败",
        message_url="https://t.me/c/1001/50",
        recipient_chat_ids=[9001],
        started_at=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 4, 13, 26, 25, tzinfo=timezone.utc),
    )
    worker = TimeoutWorker(
        queue=queue,
        alert_sender=FakeAlertSender(),
        rules_provider=lambda: [],
        task_repository=repo,
        timeout_minutes=15,
    )

    await worker.run_once(now_timestamp=1000)

    assert repo.alerted[0][0] == 20
    assert await queue.due_members(now_timestamp=1000) == []


async def test_due_sqlite_task_sends_alert_when_redis_member_is_missing(fake_redis):
    queue = RedisQueue(fake_redis)
    staff = RuleStaff(
        id=1,
        rule_id=1,
        telegram_user_id=9001,
        telegram_username="ML_YYZB3",
        display_name="YY_6/9_值班号3",
        enabled=True,
    )
    rule = MonitorRule(id=1, chat_id="-1001", chat_name="Ops", enabled=True, staff=[staff])
    task = MonitorTask(
        id=452,
        task_type="wait",
        status="pending",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=9001,
        staff_username="ML_YYZB3",
        root_message_id=825084,
        wait_message_id=825085,
        trigger_message_id=825085,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1931146238/825085",
        recipient_chat_ids=[9001],
        started_at=datetime(2026, 6, 8, 16, 38, 43, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 8, 16, 46, 43, tzinfo=timezone.utc),
    )
    repo = FakeTaskRepository()
    repo.due_tasks = [task]
    repo.tasks[452] = task
    sender = FakeAlertSender()
    worker = TimeoutWorker(
        queue=queue,
        alert_sender=sender,
        rules_provider=lambda: [rule],
        task_repository=repo,
        timeout_minutes=8,
    )

    await worker.run_once(now_timestamp=datetime(2026, 6, 8, 16, 46, 43, tzinfo=timezone.utc).timestamp())

    assert sender.sent == [(9001, 825085, 8)]
    assert repo.alerted[0][0] == 452


async def test_redis_member_is_removed_without_alert_when_db_task_is_no_longer_pending(fake_redis):
    queue = RedisQueue(fake_redis)
    pending = PendingMessage(
        task_id=452,
        task_type="wait",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        message_id=825085,
        message_time=datetime(2026, 6, 8, 16, 38, 43, tzinfo=timezone.utc),
        matched_keywords=["请稍等elk"],
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1931146238/825085",
        recipient_chat_ids=[9001],
    )
    await queue.add_pending(pending, due_at=1000)
    task = MonitorTask(
        id=452,
        task_type="wait",
        status="completed",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=9001,
        staff_username="ML_YYZB3",
        root_message_id=825084,
        wait_message_id=825085,
        trigger_message_id=825085,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1931146238/825085",
        recipient_chat_ids=[9001],
        started_at=datetime(2026, 6, 8, 16, 38, 43, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 8, 16, 46, 43, tzinfo=timezone.utc),
    )
    repo = FakeTaskRepository()
    repo.tasks[452] = task
    sender = FakeAlertSender()
    worker = TimeoutWorker(
        queue=queue,
        alert_sender=sender,
        rules_provider=lambda: [MonitorRule(id=1, chat_id="-1001", chat_name="Ops", enabled=True)],
        task_repository=repo,
        timeout_minutes=8,
    )

    await worker.run_once(now_timestamp=1000)

    assert sender.sent == []
    assert await queue.due_members(now_timestamp=1000) == []


async def test_recipient_staff_uses_repository_display_name_instead_of_chat_id(fake_redis):
    queue = RedisQueue(fake_redis)
    pending = PendingMessage(
        task_id=452,
        task_type="wait",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        message_id=825085,
        message_time=datetime(2026, 6, 8, 16, 38, 43, tzinfo=timezone.utc),
        matched_keywords=["请稍等elk"],
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1931146238/825085",
        recipient_chat_ids=[9001],
        staff_user_id=9001,
        staff_username="Y_YY_GRYBUGES",
    )
    await queue.add_pending(pending, due_at=1000)
    repo = FakeTaskRepository()
    repo.tasks[452] = MonitorTask(
        id=452,
        task_type="wait",
        status="pending",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=9001,
        staff_username="Y_YY_GRYBUGES",
        root_message_id=825084,
        wait_message_id=825085,
        trigger_message_id=825085,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1931146238/825085",
        recipient_chat_ids=[9001],
        started_at=datetime(2026, 6, 8, 16, 38, 43, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 8, 16, 46, 43, tzinfo=timezone.utc),
    )
    sender = FakeAlertSender()
    worker = TimeoutWorker(
        queue=queue,
        alert_sender=sender,
        rules_provider=lambda: [MonitorRule(id=1, chat_id="-1001", chat_name="Ops", enabled=True)],
        task_repository=repo,
        timeout_minutes=8,
    )

    await worker.run_once(now_timestamp=1000)

    assert sender.staff[0].display_name == "Y_YY_Stormrage"
    assert sender.staff[0].telegram_username == "Y_YY_GRYBUGES"


async def test_worker_removes_queue_member_when_alert_send_times_out(fake_redis):
    queue = RedisQueue(fake_redis)
    pending = PendingMessage(
        task_id=452,
        task_type="wait",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        message_id=825085,
        message_time=datetime(2026, 6, 8, 16, 38, 43, tzinfo=timezone.utc),
        matched_keywords=["请稍等elk"],
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1931146238/825085",
        recipient_chat_ids=[9001],
    )
    await queue.add_pending(pending, due_at=1000)
    repo = FakeTaskRepository()
    repo.tasks[452] = MonitorTask(
        id=452,
        task_type="wait",
        status="pending",
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=9001,
        staff_username="Y_YY_GRYBUGES",
        root_message_id=825084,
        wait_message_id=825085,
        trigger_message_id=825085,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1931146238/825085",
        recipient_chat_ids=[9001],
        started_at=datetime(2026, 6, 8, 16, 38, 43, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 8, 16, 46, 43, tzinfo=timezone.utc),
    )
    worker = TimeoutWorker(
        queue=queue,
        alert_sender=HangingAlertSender(),
        rules_provider=lambda: [MonitorRule(id=1, chat_id="-1001", chat_name="Ops", enabled=True)],
        task_repository=repo,
        timeout_minutes=8,
        send_timeout_seconds=0.01,
    )

    await worker.run_once(now_timestamp=1000)

    assert await queue.due_members(now_timestamp=1000) == []
