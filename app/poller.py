from collections.abc import Awaitable, Callable

from app.bot import _pending_from_task

MessageDeletedChecker = Callable[[str, int], Awaitable[bool]]


async def cleanup_deleted_wait_tasks(repo, queue, is_message_deleted: MessageDeletedChecker) -> None:
    tasks = [
        task
        for task in repo.list_open_tasks()
        if task.task_type in {"wait", "followup", "reply", "self_reply"}
    ]
    processed_task_ids: set[int] = set()
    for task in tasks:
        if task.id in processed_task_ids:
            continue
        if hasattr(repo, "task_context_message_ids"):
            message_ids = repo.task_context_message_ids(task.id)
        else:
            message_ids = list({task.root_message_id, task.wait_message_id, task.trigger_message_id})
        deleted_message_id = None
        for message_id in message_ids:
            if await is_message_deleted(task.chat_id, message_id):
                deleted_message_id = message_id
                break
        if deleted_message_id is None:
            continue
        if hasattr(repo, "delete_open_tasks_referencing"):
            deleted_tasks = repo.delete_open_tasks_referencing(task.chat_id, deleted_message_id)
        else:
            repo.mark_task_deleted(task.id)
            deleted_tasks = [task]
        for deleted_task in deleted_tasks:
            processed_task_ids.add(deleted_task.id)
            await queue.close_pending(deleted_task.id)

        deleted_waits = [deleted_task for deleted_task in deleted_tasks if deleted_task.task_type == "wait"]
        if not deleted_waits:
            continue
        task = deleted_waits[0]
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
