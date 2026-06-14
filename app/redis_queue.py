import json
from datetime import datetime

from app.models import PendingMessage


class RedisQueue:
    def __init__(self, redis_client):
        self.redis = redis_client

    @staticmethod
    def pending_key(task_id: int) -> str:
        return f"pending-task:{task_id}"

    @staticmethod
    def member(task_id: int) -> str:
        return str(task_id)

    @staticmethod
    def alerted_key(task_id: int) -> str:
        return f"alerted-task:{task_id}"

    async def add_pending(self, pending: PendingMessage, due_at: float) -> None:
        payload = {
            "task_id": pending.task_id,
            "task_type": pending.task_type,
            "rule_id": pending.rule_id,
            "chat_id": pending.chat_id,
            "chat_name": pending.chat_name,
            "message_id": pending.message_id,
            "message_time": pending.message_time.isoformat(),
            "matched_keywords": pending.matched_keywords,
            "message_excerpt": pending.message_excerpt,
            "message_url": pending.message_url,
            "recipient_chat_ids": pending.recipient_chat_ids,
            "staff_user_id": pending.staff_user_id,
            "staff_username": pending.staff_username,
            "status": pending.status,
        }
        await self.redis.set(self.pending_key(pending.task_id), json.dumps(payload, ensure_ascii=False))
        await self.redis.zadd("timeout_queue", {self.member(pending.task_id): due_at})

    async def get_pending(self, task_id: int) -> PendingMessage | None:
        raw = await self.redis.get(self.pending_key(task_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return PendingMessage(
            task_id=data["task_id"],
            task_type=data["task_type"],
            rule_id=data["rule_id"],
            chat_id=data["chat_id"],
            chat_name=data["chat_name"],
            message_id=data["message_id"],
            message_time=datetime.fromisoformat(data["message_time"]),
            matched_keywords=list(data["matched_keywords"]),
            message_excerpt=data["message_excerpt"],
            message_url=data["message_url"],
            recipient_chat_ids=list(data.get("recipient_chat_ids", [])),
            staff_user_id=int(data.get("staff_user_id", 0) or 0),
            staff_username=data.get("staff_username", ""),
            status=data["status"],
        )

    async def close_pending(self, task_id: int) -> None:
        await self.redis.delete(self.pending_key(task_id))
        await self.redis.delete(self.alerted_key(task_id))
        await self.redis.zrem("timeout_queue", self.member(task_id))

    async def due_members(self, now_timestamp: float, limit: int = 100) -> list[str]:
        return await self.redis.zrangebyscore("timeout_queue", 0, now_timestamp, start=0, num=limit)

    async def remove_member(self, member: str) -> None:
        await self.redis.zrem("timeout_queue", member)

    async def mark_alerted(self, task_id: int) -> bool:
        return bool(await self.redis.set(self.alerted_key(task_id), "1", nx=True))

    async def cleanup_finished_tasks(self, is_task_pending) -> list[int]:
        members = await self.redis.zrangebyscore("timeout_queue", "-inf", "+inf")
        removed: list[int] = []
        for member in members:
            text = member.decode("utf-8") if isinstance(member, bytes) else str(member)
            try:
                task_id = int(text)
            except ValueError:
                await self.redis.zrem("timeout_queue", member)
                continue
            if is_task_pending(task_id):
                continue
            await self.close_pending(task_id)
            removed.append(task_id)
        return removed
