from datetime import datetime, timezone

from app.bot import NormalizedTelegramMessage, handle_incoming_message
from app.models import KeywordConfig, MessageSnapshot, MonitorRule, MonitorTask, RuleKeyword, RuleStaff


class FakeRepo:
    def __init__(self):
        self.hits = []
        self.tasks = []
        self.context_messages = {}
        self.snapshots = {}

    def list_enabled_rules(self):
        return [
            MonitorRule(
                id=1,
                chat_id="-1001",
                chat_name="Ops",
                enabled=True,
                keywords=[RuleKeyword(id=1, rule_id=1, keyword="充值", enabled=True, note="")],
                staff=[
                    RuleStaff(
                        id=1,
                        rule_id=1,
                        telegram_user_id=9001,
                        telegram_username="agent",
                        display_name="Agent",
                        enabled=True,
                    )
                ],
            )
        ]

    def list_keyword_configs(self):
        return [KeywordConfig(keyword="请稍等elk", enabled=True, recipient_chat_ids=[10001])]

    def record_keyword_hit(self, **kwargs):
        self.hits.append(kwargs)

    def upsert_message_snapshot(self, **kwargs):
        snapshot = MessageSnapshot(**kwargs)
        self.snapshots[(snapshot.chat_id, snapshot.message_id)] = snapshot
        return snapshot

    def get_message_snapshot(self, chat_id, message_id):
        return self.snapshots.get((chat_id, message_id))

    def create_monitor_task(self, **kwargs):
        status = kwargs.pop("status", "pending")
        task = MonitorTask(id=len(self.tasks) + 1, status=status, **kwargs)
        self.tasks.append(task)
        self.context_messages[task.id] = {
            task.root_message_id,
            task.wait_message_id,
            task.trigger_message_id,
        }
        return task

    def add_task_context_message(self, task_id, message_id):
        self.context_messages.setdefault(task_id, set()).add(message_id)

    def pending_task_for_context(self, chat_id, reply_to_message_id):
        for task in reversed(self.tasks):
            if (
                task.status == "pending"
                and task.chat_id == chat_id
                and reply_to_message_id in self.context_messages.get(task.id, set())
            ):
                return task
        return None

    def complete_tasks_referencing(self, chat_id, reply_to_message_id, completed_at):
        completed = []
        for task in self.tasks:
            if (
                task.status == "pending"
                and task.chat_id == chat_id
                and reply_to_message_id in self.context_messages.get(task.id, set())
            ):
                completed_task = MonitorTask(
                    id=task.id,
                    task_type=task.task_type,
                    status="completed",
                    rule_id=task.rule_id,
                    chat_id=task.chat_id,
                    chat_name=task.chat_name,
                    keyword=task.keyword,
                    staff_user_id=task.staff_user_id,
                    staff_username=task.staff_username,
                    root_message_id=task.root_message_id,
                    wait_message_id=task.wait_message_id,
                    trigger_message_id=task.trigger_message_id,
                    message_excerpt=task.message_excerpt,
                    message_url=task.message_url,
                    recipient_chat_ids=task.recipient_chat_ids,
                    started_at=task.started_at,
                    due_at=task.due_at,
                )
                self.tasks[task.id - 1] = completed_task
                completed.append(completed_task)
        return completed

    def latest_completed_wait_for_reference(self, chat_id, message_id):
        for task in reversed(self.tasks):
            if (
                task.task_type == "wait"
                and task.status == "completed"
                and task.chat_id == chat_id
                and message_id in self.context_messages.get(task.id, set())
            ):
                return task
        return None

    def latest_pending_task_for_customer(self, chat_id, sender_user_id):
        for task in reversed(self.tasks):
            if (
                task.status == "pending"
                and task.chat_id == chat_id
                and task.task_type in {"reply", "followup"}
                and task.staff_user_id == sender_user_id
            ):
                return task
        return None

    def latest_special_processing_reply_for_message(self, chat_id, message_id, account_names):
        normalized_names = {name.lower().replace(" ", "") for name in account_names}
        for snapshot in reversed(list(self.snapshots.values())):
            display_name = getattr(snapshot, "sender_display_name", "")
            sender_names = {
                snapshot.sender_username.lower().replace(" ", ""),
                display_name.lower().replace(" ", ""),
            }
            if (
                snapshot.chat_id == chat_id
                and snapshot.reply_to_message_id == message_id
                and sender_names & normalized_names
                and "同意后处理" in snapshot.text
            ):
                return snapshot
        return None


class FakeQueue:
    def __init__(self):
        self.pending = []
        self.closed = []

    async def add_pending(self, pending, due_at):
        self.pending.append((pending, due_at))

    async def close_pending(self, task_id):
        self.closed.append(task_id)


async def test_keyword_message_records_hit_and_pending_task():
    repo = FakeRepo()
    queue = FakeQueue()
    message = NormalizedTelegramMessage(
        chat_id="-1001",
        chat_name="Ops",
        chat_username="",
        message_id=50,
        sender_user_id=10001,
        sender_username="elk",
        text="请稍等elk",
        message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        reply_to_message_id=None,
    )

    await handle_incoming_message(message, repo, queue, timeout_minutes=15, now_timestamp=1000)

    assert repo.hits[0]["matched_keyword"] == "请稍等elk"
    assert repo.tasks[0].task_type == "wait"
    assert repo.tasks[0].due_at.minute == 19
    assert queue.pending[0][0].matched_keywords == ["请稍等elk"]
    assert queue.pending[0][1] == 1480


async def test_keyword_with_alert_disabled_records_hit_without_task():
    class NoAlertRepo(FakeRepo):
        def list_keyword_configs(self):
            return [
                KeywordConfig(
                    keyword="请稍等elk",
                    enabled=True,
                    alert_enabled=False,
                    recipient_chat_ids=[10001],
                )
            ]

    repo = NoAlertRepo()
    queue = FakeQueue()
    message = NormalizedTelegramMessage(
        chat_id="-1001",
        chat_name="Ops",
        chat_username="",
        message_id=50,
        sender_user_id=10001,
        sender_username="elk",
        text="请稍等elk",
        message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        reply_to_message_id=None,
    )

    await handle_incoming_message(message, repo, queue, timeout_minutes=15, now_timestamp=1000)

    assert repo.hits[0]["matched_keyword"] == "请稍等elk"
    assert repo.tasks == []
    assert queue.pending == []


async def test_staff_reply_completes_wait_task():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=50,
            sender_user_id=10001,
            sender_username="elk",
            text="请稍等elk",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=40,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=51,
            sender_user_id=10001,
            sender_username="elk",
            text="已处理",
            message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
            reply_to_message_id=50,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1060,
    )

    assert repo.tasks[0].status == "completed"
    assert queue.closed == [1]


async def test_customer_requote_completed_wait_creates_followup_task():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=50,
            sender_user_id=10001,
            sender_username="elk",
            text="请稍等elk",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=40,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )
    repo.complete_tasks_referencing("-1001", 50, datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc))

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=60,
            sender_user_id=20001,
            sender_username="customer",
            text="这个再看下",
            message_time=datetime(2026, 6, 4, 13, 20, 25, tzinfo=timezone.utc),
            reply_to_message_id=50,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1540,
    )

    assert repo.tasks[1].task_type == "followup"
    assert repo.tasks[1].due_at.minute == 35
    assert queue.pending[-1][0].task_type == "followup"
    assert queue.pending[-1][1] == datetime(2026, 6, 4, 13, 35, 25, tzinfo=timezone.utc).timestamp()


async def test_processing_staff_reply_keeps_followup_task_pending():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=50,
            sender_user_id=10001,
            sender_username="elk",
            text="请稍等elk",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=40,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )
    repo.complete_tasks_referencing("-1001", 50, datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc))
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=60,
            sender_user_id=20001,
            sender_username="customer",
            text="这个再看下",
            message_time=datetime(2026, 6, 4, 13, 20, 25, tzinfo=timezone.utc),
            reply_to_message_id=50,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1540,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=61,
            sender_user_id=10001,
            sender_username="elk",
            text="核实中",
            message_time=datetime(2026, 6, 4, 13, 21, 25, tzinfo=timezone.utc),
            reply_to_message_id=60,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1600,
    )

    assert repo.tasks[1].task_type == "followup"
    assert repo.tasks[1].status == "pending"
    assert queue.closed == []


async def test_ignored_customer_requote_does_not_create_followup_task():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=50,
            sender_user_id=10001,
            sender_username="elk",
            text="请稍等elk",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=40,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )
    repo.complete_tasks_referencing("-1001", 50, datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc))

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=60,
            sender_user_id=20001,
            sender_username="customer",
            text="好的",
            message_time=datetime(2026, 6, 4, 13, 20, 25, tzinfo=timezone.utc),
            reply_to_message_id=50,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1540,
    )

    assert len(repo.tasks) == 1
    assert queue.pending[-1][0].task_type == "wait"


async def test_customer_reply_to_staff_message_does_not_create_reply_task():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=80,
            sender_user_id=10001,
            sender_username="elk",
            text="我看一下",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=81,
            sender_user_id=20001,
            sender_username="customer",
            text="这个还没好",
            message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
            reply_to_message_id=80,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1060,
    )

    assert repo.tasks == []
    assert queue.pending == []


async def test_customer_non_reply_without_enabled_keyword_creates_reply_task_for_all_alert_recipients():
    class MultiRecipientRepo(FakeRepo):
        def list_keyword_configs(self):
            return [
                KeywordConfig(keyword="请稍等elk", enabled=True, recipient_chat_ids=[10001], alert_enabled=True),
                KeywordConfig(keyword="请稍等ART", enabled=True, recipient_chat_ids=[10002], alert_enabled=True),
                KeywordConfig(keyword="请稍等MAD", enabled=True, recipient_chat_ids=[10003], alert_enabled=False),
            ]

    repo = MultiRecipientRepo()
    queue = FakeQueue()

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=90,
            sender_user_id=20001,
            sender_username="customer",
            text="这个订单怎么还没处理",
            message_time=datetime(2026, 6, 4, 13, 14, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1180,
    )

    assert repo.tasks[-1].task_type == "reply"
    assert repo.tasks[-1].recipient_chat_ids == [10001, 10002]
    assert repo.tasks[-1].due_at.minute == 19
    assert queue.pending[-1][0].task_type == "reply"
    assert queue.pending[-1][1] == datetime(2026, 6, 4, 13, 19, 25, tzinfo=timezone.utc).timestamp()


async def test_customer_non_reply_with_enabled_keyword_does_not_create_reply_task():
    repo = FakeRepo()
    queue = FakeQueue()

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=91,
            sender_user_id=20001,
            sender_username="customer",
            text="请稍等elk",
            message_time=datetime(2026, 6, 4, 13, 14, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1180,
    )

    assert repo.tasks == []
    assert queue.pending == []


async def test_ignored_customer_reply_to_staff_message_does_not_create_reply_task():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=80,
            sender_user_id=10001,
            sender_username="elk",
            text="我看一下",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=81,
            sender_user_id=20001,
            sender_username="customer",
            text="D",
            message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
            reply_to_message_id=80,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1060,
    )

    assert repo.tasks == []
    assert queue.pending == []


async def test_unconfigured_chat_reply_to_staff_does_not_create_reply_task_or_snapshot():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1002",
            chat_name="Other",
            chat_username="",
            message_id=80,
            sender_user_id=10001,
            sender_username="elk",
            text="staff message",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1002",
            chat_name="Other",
            chat_username="",
            message_id=81,
            sender_user_id=20001,
            sender_username="customer",
            text="@staff please check",
            message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
            reply_to_message_id=80,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1060,
    )

    assert repo.snapshots == {}
    assert repo.tasks == []
    assert queue.pending == []


async def test_customer_supplement_without_keyword_creates_reply_task():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=80,
            sender_user_id=10001,
            sender_username="elk",
            text="我看一下",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=81,
            sender_user_id=20001,
            sender_username="customer",
            text="这个还没好",
            message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
            reply_to_message_id=80,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1060,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=82,
            sender_user_id=20001,
            sender_username="customer",
            text="再补充一下订单号",
            message_time=datetime(2026, 6, 4, 13, 13, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1120,
    )

    assert repo.tasks[-1].task_type == "reply"
    assert repo.tasks[-1].due_at.minute == 18
    assert queue.pending[-1][0].task_type == "reply"


async def test_approval_after_special_processing_account_creates_self_reply_task():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=100,
            sender_user_id=20001,
            sender_username="customer",
            text="需要处理这个订单",
            message_time=datetime(2026, 6, 4, 13, 10, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=940,
    )
    repo.tasks.clear()
    queue.pending.clear()

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=101,
            sender_user_id=30001,
            sender_username="",
            sender_display_name="Y_YY_grybuges",
            text="@领导同意后处理",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=100,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=102,
            sender_user_id=40001,
            sender_username="leader",
            text="确认",
            message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
            reply_to_message_id=101,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1060,
    )

    assert repo.tasks[-1].task_type == "self_reply"
    assert repo.tasks[-1].due_at.minute == 22
    assert queue.pending[-1][0].task_type == "self_reply"
    assert queue.pending[-1][1] == datetime(2026, 6, 4, 13, 22, 25, tzinfo=timezone.utc).timestamp()


async def test_ignored_customer_supplement_does_not_create_self_reply_task():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=80,
            sender_user_id=10001,
            sender_username="elk",
            text="我看一下",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=81,
            sender_user_id=20001,
            sender_username="customer",
            text="这个还没好",
            message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
            reply_to_message_id=80,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1060,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=82,
            sender_user_id=20001,
            sender_username="customer",
            text="1",
            message_time=datetime(2026, 6, 4, 13, 13, 25, tzinfo=timezone.utc),
            reply_to_message_id=None,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1120,
    )

    assert repo.tasks == []
    assert queue.pending == []


async def test_customer_supplement_to_wait_becomes_context_for_completion():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=50,
            sender_user_id=10001,
            sender_username="elk",
            text="请稍等elk",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=40,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=60,
            sender_user_id=20001,
            sender_username="customer",
            text="补充一下，是订单123",
            message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
            reply_to_message_id=50,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1060,
    )

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=61,
            sender_user_id=10001,
            sender_username="elk",
            text="已查询好",
            message_time=datetime(2026, 6, 4, 13, 13, 25, tzinfo=timezone.utc),
            reply_to_message_id=60,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1120,
    )

    assert 60 in repo.context_messages[1]
    assert repo.tasks[0].status == "completed"
    assert queue.closed == [1]


async def test_customer_requote_context_after_completion_creates_followup_task():
    repo = FakeRepo()
    queue = FakeQueue()
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=50,
            sender_user_id=10001,
            sender_username="elk",
            text="请稍等elk",
            message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
            reply_to_message_id=40,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1000,
    )
    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=60,
            sender_user_id=20001,
            sender_username="customer",
            text="补充一下",
            message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
            reply_to_message_id=50,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1060,
    )
    repo.complete_tasks_referencing("-1001", 60, datetime(2026, 6, 4, 13, 13, 25, tzinfo=timezone.utc))

    await handle_incoming_message(
        NormalizedTelegramMessage(
            chat_id="-1001",
            chat_name="Ops",
            chat_username="",
            message_id=70,
            sender_user_id=20001,
            sender_username="customer",
            text="这个再催一下",
            message_time=datetime(2026, 6, 4, 13, 20, 25, tzinfo=timezone.utc),
            reply_to_message_id=60,
        ),
        repo,
        queue,
        timeout_minutes=15,
        now_timestamp=1540,
    )

    assert repo.tasks[1].task_type == "followup"
    assert repo.tasks[1].root_message_id == 40
    assert repo.tasks[1].trigger_message_id == 70
