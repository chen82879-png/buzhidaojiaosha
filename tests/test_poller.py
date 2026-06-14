from datetime import datetime, timedelta, timezone

from app.db import connect, migrate
from app.models import KeywordConfig
from app.poller import cleanup_deleted_wait_tasks
from app.repositories import Repository


class FakeQueue:
    def __init__(self):
        self.closed = []
        self.pending = []

    async def close_pending(self, task_id):
        self.closed.append(task_id)

    async def add_pending(self, pending, due_at):
        self.pending.append((pending, due_at))


def make_repo(tmp_path):
    conn = connect(str(tmp_path / "app.sqlite3"))
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id="-1001", chat_name="Ops", enabled=True)
    return repo, rule_id


async def test_deleted_first_wait_promotes_duplicate_when_keyword_is_configured(tmp_path):
    repo, rule_id = make_repo(tmp_path)
    repo.save_keyword_configs([KeywordConfig(keyword="请稍等elk", enabled=True, recipient_chat_ids=[7511822833])])
    started = datetime(2026, 6, 4, 13, 0, tzinfo=timezone.utc)
    repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=40,
        wait_message_id=50,
        trigger_message_id=50,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1001/50",
        recipient_chat_ids=[7511822833],
        started_at=started,
        due_at=started + timedelta(minutes=8),
    )
    repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=40,
        wait_message_id=51,
        trigger_message_id=51,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1001/51",
        recipient_chat_ids=[7511822833],
        started_at=started + timedelta(minutes=1),
        due_at=started + timedelta(minutes=9),
        status="duplicate",
    )
    queue = FakeQueue()

    async def deleted(_chat_id, message_id):
        return message_id == 50

    await cleanup_deleted_wait_tasks(repo, queue, deleted)

    assert repo.get_monitor_task(1).status == "deleted"
    assert repo.get_monitor_task(2).status == "pending"
    assert queue.closed == [1]
    assert queue.pending[0][0].task_id == 2


async def test_deleted_first_wait_ignores_duplicate_when_keyword_is_not_configured(tmp_path):
    repo, rule_id = make_repo(tmp_path)
    repo.save_keyword_configs([KeywordConfig(keyword="请稍等elk", enabled=False, recipient_chat_ids=[])])
    started = datetime(2026, 6, 4, 13, 0, tzinfo=timezone.utc)
    repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=40,
        wait_message_id=50,
        trigger_message_id=50,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1001/50",
        recipient_chat_ids=[7511822833],
        started_at=started,
        due_at=started + timedelta(minutes=8),
    )
    repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=40,
        wait_message_id=51,
        trigger_message_id=51,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1001/51",
        recipient_chat_ids=[],
        started_at=started + timedelta(minutes=1),
        due_at=started + timedelta(minutes=9),
        status="duplicate",
    )
    queue = FakeQueue()

    async def deleted(_chat_id, message_id):
        return message_id == 50

    await cleanup_deleted_wait_tasks(repo, queue, deleted)

    assert repo.get_monitor_task(1).status == "deleted"
    assert repo.get_monitor_task(2).status == "deleted"
    assert queue.pending == []

