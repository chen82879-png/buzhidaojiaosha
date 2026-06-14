from datetime import datetime, timezone

from app.models import PendingMessage
from app.redis_queue import RedisQueue


async def test_adds_pending_message_and_due_timeout(fake_redis):
    queue = RedisQueue(fake_redis)
    pending = PendingMessage(
        task_id=12,
        task_type="wait",
        rule_id=1,
        chat_id="-1001571955528",
        chat_name="Ops",
        message_id=398744,
        message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        matched_keywords=["充值"],
        message_excerpt="充值失败",
        message_url="https://t.me/c/1571955528/398744",
    )

    await queue.add_pending(pending, due_at=1000)
    loaded = await queue.get_pending(12)
    due = await queue.due_members(now_timestamp=1000)

    assert loaded == pending
    assert due == ["12"]


async def test_alert_dedupe_only_allows_first_mark(fake_redis):
    queue = RedisQueue(fake_redis)

    assert await queue.mark_alerted(10) is True
    assert await queue.mark_alerted(10) is False


async def test_cleanup_finished_tasks_removes_non_pending_members(fake_redis):
    queue = RedisQueue(fake_redis)
    pending = PendingMessage(
        task_id=12,
        task_type="wait",
        rule_id=1,
        chat_id="-1001571955528",
        chat_name="Ops",
        message_id=398744,
        message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        matched_keywords=["充值"],
        message_excerpt="充值失败",
        message_url="https://t.me/c/1571955528/398744",
    )
    stale = PendingMessage(
        task_id=13,
        task_type="reply",
        rule_id=1,
        chat_id="-1001571955528",
        chat_name="Ops",
        message_id=398745,
        message_time=datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
        matched_keywords=["客户回复客服"],
        message_excerpt="客户追问",
        message_url="https://t.me/c/1571955528/398745",
    )
    await queue.add_pending(pending, due_at=1000)
    await queue.add_pending(stale, due_at=1001)
    await queue.mark_alerted(13)

    removed = await queue.cleanup_finished_tasks(lambda task_id: task_id == 12)

    assert removed == [13]
    assert await queue.get_pending(12) == pending
    assert await queue.get_pending(13) is None
    assert await queue.due_members(now_timestamp=1001) == ["12"]
    assert await fake_redis.get(queue.alerted_key(13)) is None
