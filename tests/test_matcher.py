from app.matcher import match_message
from app.models import MonitorRule, RuleKeyword, RuleStaff


def test_disabled_chat_rule_is_ignored():
    rule = MonitorRule(
        id=1,
        chat_id="-1001",
        chat_name="Ops",
        enabled=False,
        keywords=[RuleKeyword(id=1, rule_id=1, keyword="充值", enabled=True, note="")],
        staff=[],
    )

    assert match_message(chat_id="-1001", text="充值失败", rules=[rule]) is None


def test_enabled_chat_and_fixed_keyword_returns_matched_keywords():
    rule = MonitorRule(
        id=1,
        chat_id="-1001",
        chat_name="Ops",
        enabled=True,
        keywords=[],
        staff=[
            RuleStaff(
                id=1,
                rule_id=1,
                telegram_user_id=9001,
                telegram_username="agent",
                display_name="Agent",
                enabled=True,
            )
        ],
    )

    result = match_message(chat_id="-1001", text="请稍等elk", rules=[rule])

    assert result is not None
    assert result.rule.id == 1
    assert result.matched_keywords == ["请稍等elk"]


def test_enabled_chat_uses_fixed_keywords_without_rule_keyword_bindings():
    rule = MonitorRule(
        id=1,
        chat_id="-1001",
        chat_name="Ops",
        enabled=True,
        keywords=[],
        staff=[],
    )

    result = match_message(chat_id="-1001", text="请稍等-MAD", rules=[rule])

    assert result is not None
    assert result.rule.id == 1
    assert result.matched_keywords == ["请稍等-MAD"]


def test_enabled_chat_uses_fixed_keywords_even_when_legacy_rule_keywords_exist():
    rule = MonitorRule(
        id=1,
        chat_id="-1001",
        chat_name="Ops",
        enabled=True,
        keywords=[RuleKeyword(id=1, rule_id=1, keyword="请稍等elk", enabled=True, note="legacy")],
        staff=[],
    )

    result = match_message(chat_id="-1001", text="请稍等ART", rules=[rule])

    assert result is not None
    assert result.rule.id == 1
    assert result.matched_keywords == ["请稍等ART"]
