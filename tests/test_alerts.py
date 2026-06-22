from datetime import datetime, timezone

from app.alerts import render_timeout_alert
from app.models import PendingMessage, RuleStaff


def test_wait_timeout_alert_uses_names_usernames_and_no_bare_recipient_chat_id():
    staff = RuleStaff(
        id=1,
        rule_id=1,
        telegram_user_id=7511822833,
        telegram_username="ML_YYZB3",
        display_name="YY_6/9_值班号3【拒绝私聊】",
        enabled=True,
    )
    pending = PendingMessage(
        task_id=20,
        task_type="wait",
        rule_id=1,
        chat_id="-1001571955528",
        chat_name="9-YY-DL对接",
        message_id=398744,
        message_time=datetime(2026, 6, 5, 21, 11, 25, tzinfo=timezone.utc),
        matched_keywords=["请稍等elk"],
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1571955528/398744",
        recipient_chat_ids=[7511822833],
    )

    text = render_timeout_alert(staff, pending, timeout_minutes=8)

    assert "接收人员：YY_6/9_值班号3【拒绝私聊】 (@ML_YYZB3)" in text
    assert "客服：请稍等elk" in text
    assert "状态：稍等任务 8 分钟无引用回复" in text
    assert "原因：客服发送稍等后，后续未发现有效引用回复" in text
    assert "原消息链接：打开原消息\nhttps://t.me/c/1571955528/398744" in text
    assert "7511822833" not in text


def test_followup_timeout_alert_uses_followup_reason():
    staff = RuleStaff(
        id=1,
        rule_id=1,
        telegram_user_id=7511822833,
        telegram_username="ML_YYZB3",
        display_name="YY_6/9_值班号3【拒绝私聊】",
        enabled=True,
    )
    pending = PendingMessage(
        task_id=21,
        task_type="followup",
        rule_id=1,
        chat_id="-1001571955528",
        chat_name="9-YY-DL对接",
        message_id=398760,
        message_time=datetime(2026, 6, 5, 21, 26, 25, tzinfo=timezone.utc),
        matched_keywords=["请稍等elk"],
        message_excerpt="这个再看下",
        message_url="https://t.me/c/1571955528/398760",
        recipient_chat_ids=[7511822833],
    )

    text = render_timeout_alert(staff, pending, timeout_minutes=15)

    assert "状态：跟进任务 15 分钟无引用回复" in text
    assert "原因：客服回复继续处理后，未发现后续有效引用回复" in text
