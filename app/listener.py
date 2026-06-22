import asyncio
import time

from redis import asyncio as redis_async
from telethon import TelegramClient, events

from app.bot import NormalizedTelegramMessage, handle_incoming_message
from app.config import Settings, load_settings
from app.db import connect, migrate
from app.group_configurator import configure_monitor_groups_from_dialogs
from app.poller import cleanup_deleted_wait_tasks
from app.redis_queue import RedisQueue
from app.repositories import Repository
from app.staff_identity import StaffIdentity
from app.work_mode import WorkModeController


def normalize_telethon_message(message) -> NormalizedTelegramMessage | None:
    text = getattr(message, "text", "") or getattr(message, "raw_text", "") or ""
    has_media = bool(getattr(message, "media", None))
    if not text:
        if not has_media:
            return None
        text = "[媒体消息]"
    chat = getattr(message, "chat", None)
    sender = getattr(message, "sender", None)
    chat_id = str(getattr(message, "chat_id", ""))
    return NormalizedTelegramMessage(
        chat_id=chat_id,
        chat_name=getattr(chat, "title", None) or getattr(chat, "first_name", None) or chat_id,
        chat_username=getattr(chat, "username", None) or "",
        message_id=int(getattr(message, "id")),
        sender_user_id=int(getattr(message, "sender_id", 0) or 0),
        sender_username=getattr(sender, "username", None) or "",
        sender_display_name=" ".join(
            value for value in (
                getattr(sender, "first_name", None),
                getattr(sender, "last_name", None),
            ) if value
        ),
        text=text,
        message_time=getattr(message, "date"),
        reply_to_message_id=getattr(message, "reply_to_msg_id", None),
        media_group_id=getattr(message, "grouped_id", None),
        message_kind="media" if has_media else "text",
    )


async def run_listener(settings: Settings | None = None) -> None:
    settings = settings or load_settings()
    conn = connect(settings.sqlite_path)
    migrate(conn)
    repo = Repository(conn)
    queue = RedisQueue(redis_async.from_url(settings.redis_url, decode_responses=True))
    client = TelegramClient(settings.telethon_session_path, settings.telegram_api_id, settings.telegram_api_hash)
    staff_identity = StaffIdentity.source_defaults(extra_ids=settings.other_cs_ids)

    async def clear_runtime() -> None:
        repo.clear_active_runtime_tasks()
        await queue.clear_runtime()

    work_mode = WorkModeController(clear_runtime=clear_runtime)
    listener_user_id = 0

    @client.on(events.NewMessage)
    async def on_new_message(event):
        if int(getattr(event, "chat_id", 0) or 0) == listener_user_id:
            response = await work_mode.handle_command(getattr(event.message, "text", ""))
            if response is not None:
                await event.reply(response)
                return
        normalized = normalize_telethon_message(event.message)
        if normalized is None:
            return
        await handle_incoming_message(
            normalized,
            repo,
            queue,
            settings.global_timeout_minutes,
            time.time(),
            staff_identity=staff_identity,
            keep_keywords=settings.keep_keywords,
            work_mode=work_mode,
        )

    @client.on(events.MessageEdited)
    async def on_message_edited(event):
        normalized = normalize_telethon_message(event.message)
        if normalized is None:
            return
        if hasattr(repo, "cancel_tasks_referencing"):
            cancelled = repo.cancel_tasks_referencing(
                normalized.chat_id,
                normalized.message_id,
                status="completed" if normalized.reply_to_message_id else "deleted",
            )
            for task in cancelled:
                await queue.close_pending(task.id)
        await handle_incoming_message(
            normalized,
            repo,
            queue,
            settings.global_timeout_minutes,
            time.time(),
            staff_identity=staff_identity,
            keep_keywords=settings.keep_keywords,
            work_mode=work_mode,
        )

    async def message_deleted(chat_id: str, message_id: int) -> bool:
        try:
            message = await client.get_messages(int(chat_id), ids=message_id)
        except Exception:
            return False
        return message is None

    async def polling_loop() -> None:
        while True:
            await cleanup_deleted_wait_tasks(repo, queue, message_deleted)
            await asyncio.sleep(60)

    await client.start(phone=settings.listener_phone)
    me = await client.get_me()
    listener_user_id = int(getattr(me, "id", 0) or 0)
    staff_identity = StaffIdentity.source_defaults(
        listener_user_id=listener_user_id,
        extra_ids=settings.other_cs_ids,
    )
    await configure_monitor_groups_from_dialogs(repo, client)
    asyncio.create_task(polling_loop())
    await client.run_until_disconnected()


def main() -> int:
    asyncio.run(run_listener())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
