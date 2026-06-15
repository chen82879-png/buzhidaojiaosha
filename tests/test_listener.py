from datetime import timezone
from types import SimpleNamespace

from app.listener import normalize_telethon_message


def test_normalizes_telethon_message_with_reply():
    message = SimpleNamespace(
        chat_id=7511822833,
        id=398744,
        text="请稍等elk",
        date=__import__("datetime").datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        sender_id=10001,
        reply_to_msg_id=398700,
        chat=SimpleNamespace(title="test-chat", username=""),
        sender=SimpleNamespace(username="customer_a", first_name="Customer", last_name="A"),
    )

    normalized = normalize_telethon_message(message)

    assert normalized.chat_id == "7511822833"
    assert normalized.chat_name == "test-chat"
    assert normalized.message_id == 398744
    assert normalized.sender_user_id == 10001
    assert normalized.sender_username == "customer_a"
    assert normalized.sender_display_name == "Customer A"
    assert normalized.text == "请稍等elk"
    assert normalized.reply_to_message_id == 398700


def test_normalizes_telethon_media_reply_without_text():
    message = SimpleNamespace(
        chat_id=7511822833,
        id=398745,
        text="",
        raw_text="",
        media=object(),
        date=__import__("datetime").datetime(2026, 6, 4, 13, 12, 25, tzinfo=timezone.utc),
        sender_id=9001,
        reply_to_msg_id=398744,
        chat=SimpleNamespace(title="test-chat", username=""),
        sender=SimpleNamespace(username="agent"),
    )

    normalized = normalize_telethon_message(message)

    assert normalized is not None
    assert normalized.text == "[媒体消息]"
    assert normalized.reply_to_message_id == 398744
    assert normalized.sender_user_id == 9001


def test_ignores_telethon_message_without_text_or_media():
    message = SimpleNamespace(
        chat_id=7511822833,
        id=398744,
        text="",
        raw_text="",
        date=__import__("datetime").datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        sender_id=10001,
        reply_to_msg_id=None,
        chat=SimpleNamespace(title="test-chat", username=""),
        sender=SimpleNamespace(username="customer_a"),
    )

    assert normalize_telethon_message(message) is None
