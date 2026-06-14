from app.telegram_utils import build_message_url


def test_builds_private_supergroup_message_url():
    assert build_message_url(chat_id="-1001571955528", message_id=398744, username="") == (
        "https://t.me/c/1571955528/398744"
    )


def test_builds_public_chat_message_url():
    assert build_message_url(chat_id="-100111", message_id=42, username="public_ops") == (
        "https://t.me/public_ops/42"
    )
