from collections.abc import Awaitable, Callable

from app.bot import _pending_from_task

MessageDeletedChecker = Callable[[str, int], Awaitable[bool]]


async def cleanup_deleted_wait_tasks(repo, queue, is_message_deleted: MessageDeletedChecker) -> None:
    tasks = [
        task
        for task in repo.list_open_tasks()
        if task.task_type in {"wait", "followup", "reply", "self_reply"}
    ]
    for task in tasks:
        if not (
            await is_message_deleted(task.chat_id, task.wait_message_id)
            or await is_message_deleted(task.chat_id, task.trigger_message_id)
        ):
            continue
        repo.mark_task_deleted(task.id)
        await queue.close_pending(task.id)

        if task.task_type != "wait":
            continue
        while True:
            duplicate = repo.earliest_duplicate_wait_for_reference(task.chat_id, task.root_message_id)
            if duplicate is None:
                break
            if await is_message_deleted(duplicate.chat_id, duplicate.wait_message_id):
                repo.mark_task_deleted(duplicate.id)
                continue
            config = repo.enabled_keyword_config(duplicate.keyword)
            if config is None:
                repo.mark_task_deleted(duplicate.id)
                break
            promoted = repo.activate_duplicate_task(duplicate.id)
            await queue.add_pending(
                _pending_from_task(promoted, config.recipient_chat_ids),
                due_at=promoted.due_at.timestamp(),
            )
            break
