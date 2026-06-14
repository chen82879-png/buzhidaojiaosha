from app.models import MonitorRule, RuleKeyword, RuleStaff
from app.response_detector import IncomingMessage, detect_staff_response


def test_staff_quoted_reply_closes_pending_message():
    rule = MonitorRule(
        id=1,
        chat_id="-1001",
        chat_name="Ops",
        enabled=True,
        keywords=[RuleKeyword(id=1, rule_id=1, keyword="充值", enabled=True, note="")],
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
    message = IncomingMessage(chat_id="-1001", sender_user_id=9001, message_id=51, reply_to_message_id=50)

    assert detect_staff_response(message, [rule]) == ("-1001", 50)


def test_staff_non_reply_does_not_close_pending_message():
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
    message = IncomingMessage(chat_id="-1001", sender_user_id=9001, message_id=51, reply_to_message_id=None)

    assert detect_staff_response(message, [rule]) is None
