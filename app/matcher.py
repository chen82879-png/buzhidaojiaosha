from dataclasses import dataclass

from app.fixed_keywords import FIXED_KEYWORDS
from app.models import KeywordConfig, MonitorRule


@dataclass(frozen=True)
class MatchResult:
    rule: MonitorRule
    matched_keywords: list[str]


def match_message(chat_id: str, text: str, rules: list[MonitorRule]) -> MatchResult | None:
    for rule in rules:
        if not rule.enabled or rule.chat_id != chat_id:
            continue
        matched = [keyword for keyword in FIXED_KEYWORDS if keyword in text]
        if matched:
            return MatchResult(rule=rule, matched_keywords=matched)
    return None


def match_enabled_keyword(text: str, configs: list[KeywordConfig]) -> KeywordConfig | None:
    for config in configs:
        if config.enabled and config.task_enabled and config.keyword in text:
            return config
    return None
