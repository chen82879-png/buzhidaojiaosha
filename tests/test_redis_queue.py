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


async def test_add_and_close_severe_queue_member(fake_redis):
    queue = RedisQueue(fake_redis)

    await queue.add_severe(task_id=20, due_at=1600)

    assert await queue.due_severe_members(1600) == ["20"]
    await queue.close_pending(20)
    assert await queue.due_severe_members(1600) == []


async def test_clear_runtime_removes_all_timeout_state(fake_redis):
    queue = RedisQueue(fake_redis)
    pending = PendingMessage(
        task_id=21, task_type="wait", rule_id=1, chat_id="-1001", chat_name="Ops",
        message_id=50, message_time=datetime.now(timezone.utc), matched_keywords=["请稍等elk"],
        message_excerpt="请稍等elk", message_url="https://t.me/c/1/50",
    )
    await queue.add_pending(pending, due_at=1000)
    await queue.add_severe(21, due_at=1600)
    await queue.mark_alerted(21)
    await queue.mark_severe_alerted(21)

    await queue.clear_runtime()

    assert await queue.get_pending(21) is None
    assert await queue.due_members(float("inf")) == []
    assert await queue.due_severe_members(float("inf")) == []
    assert await queue.mark_alerted(21) is True
    assert await queue.mark_severe_alerted(21) is True
