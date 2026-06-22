from app.alert_rules import (
    FOLLOWUP_TIMEOUT_MINUTES,
    IGNORE_WORDS,
    REPLY_TIMEOUT_MINUTES,
    SELF_REPLY_TIMEOUT_MINUTES,
    SEVERE_WAIT_TOTAL_MINUTES,
    WAIT_TIMEOUT_MINUTES,
    is_followup_keyword,
    is_ignored_customer_text,
)


def test_source_timeout_values():
    assert WAIT_TIMEOUT_MINUTES == 12
    assert SEVERE_WAIT_TOTAL_MINUTES == 22
    assert FOLLOWUP_TIMEOUT_MINUTES == 15
    assert REPLY_TIMEOUT_MINUTES == 5
    assert SELF_REPLY_TIMEOUT_MINUTES == 3


def test_ignore_words_use_normalized_exact_match():
    assert "好的" in IGNORE_WORDS
    assert is_ignored_customer_text(" 好的。")
    assert not is_ignored_customer_text("好的，查询123")


def test_followup_keywords_are_exact():
    assert is_followup_keyword("核实中", ("核实中", "处理中"))
    assert not is_followup_keyword("正在核实中，请稍等", ("核实中", "处理中"))
