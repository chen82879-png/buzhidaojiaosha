import pytest

from app.ai_audit import (
    EXCLUDED_CHAT_IDS,
    LOOKBACK_HOURS,
    GeminiDecision,
    parse_gemini_decision,
)


def test_source_audit_windows_and_excluded_groups():
    assert LOOKBACK_HOURS == {"off_duty": 10, "ordinary": 12, "full": 20}
    assert EXCLUDED_CHAT_IDS == {"-1002807120955", "-1002169616907"}


def test_parse_json_decision_from_markdown_fence():
    result = parse_gemini_decision('```json\n{"needs_review": false, "reason": "已明确回复"}\n```')
    assert result == GeminiDecision(needs_review=False, reason="已明确回复")


@pytest.mark.parametrize("raw", ["", "not json", "{}", '{"needs_review": "no"}'])
def test_invalid_ai_output_is_conservative(raw):
    result = parse_gemini_decision(raw)
    assert result.needs_review is True
    assert "人工复核" in result.reason
