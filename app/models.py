from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RuleKeyword:
    id: int
    rule_id: int
    keyword: str
    enabled: bool
    note: str


@dataclass(frozen=True)
class RuleStaff:
    id: int
    rule_id: int
    telegram_user_id: int
    telegram_username: str
    display_name: str
    enabled: bool


@dataclass(frozen=True)
class MonitorRule:
    id: int
    chat_id: str
    chat_name: str
    enabled: bool
    keywords: list[RuleKeyword] = field(default_factory=list)
    staff: list[RuleStaff] = field(default_factory=list)


@dataclass(frozen=True)
class PendingMessage:
    task_id: int
    task_type: str
    rule_id: int
    chat_id: str
    chat_name: str
    message_id: int
    message_time: datetime
    matched_keywords: list[str]
    message_excerpt: str
    message_url: str
    recipient_chat_ids: list[int] = field(default_factory=list)
    staff_user_id: int = 0
    staff_username: str = ""
    status: str = "pending"


@dataclass(frozen=True)
class KeywordConfig:
    keyword: str
    enabled: bool
    recipient_chat_ids: list[int]
    alert_enabled: bool = True


@dataclass(frozen=True)
class MonitorTask:
    id: int
    task_type: str
    status: str
    rule_id: int
    chat_id: str
    chat_name: str
    keyword: str
    staff_user_id: int
    staff_username: str
    root_message_id: int
    wait_message_id: int
    trigger_message_id: int
    message_excerpt: str
    message_url: str
    recipient_chat_ids: list[int]
    started_at: datetime
    due_at: datetime


@dataclass(frozen=True)
class MessageSnapshot:
    chat_id: str
    message_id: int
    sender_user_id: int
    sender_username: str
    is_staff: bool
    text: str
    message_time: datetime
    reply_to_message_id: int | None = None
