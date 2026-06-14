import pytest

from app.ignore_words import is_continuing_staff_reply_text


@pytest.mark.parametrize("text", ["=", "稍等", "1", "核实中", "还没好", "再处理"])
def test_continuing_staff_reply_words_keep_followup_pending(text):
    assert is_continuing_staff_reply_text(text) is True


@pytest.mark.parametrize("text", ["已经处理好了", "已回", "查好了"])
def test_completion_staff_reply_words_can_close_followup(text):
    assert is_continuing_staff_reply_text(text) is False
