from dataclasses import dataclass

from app.models import MonitorRule


@dataclass(frozen=True)
class IncomingMessage:
    chat_id: str
    sender_user_id: int
    message_id: int
    reply_to_message_id: int | None


def detect_staff_response(message: IncomingMessage, rules: list[MonitorRule]) -> tuple[str, int] | None:
    if message.reply_to_message_id is None:
        return None
    for rule in rules:
        if not rule.enabled or rule.chat_id != message.chat_id:
            continue
        staff_ids = {staff.telegram_user_id for staff in rule.staff if staff.enabled}
        if message.sender_user_id in staff_ids:
            return (message.chat_id, message.reply_to_message_id)
    return None
