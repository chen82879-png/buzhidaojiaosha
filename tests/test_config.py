import pytest

from app.config import Settings, validate_settings


def test_validate_settings_accepts_zeabur_data_paths():
    settings = Settings(
        telegram_bot_token="123:abc",
        webhook_url="https://example.com/webhook/telegram",
        redis_url="redis://example:6379/0",
        sqlite_path="/data/telegram_alert_bot.sqlite3",
        admin_password="secret",
        global_timeout_minutes=15,
        telegram_api_id=123456,
        telegram_api_hash="hash",
        listener_phone="+10000000000",
        telethon_session_path="/data/listener.session",
    )

    validate_settings(settings)


def test_validate_settings_rejects_missing_token():
    settings = Settings(
        telegram_bot_token="",
        webhook_url="https://example.com/webhook/telegram",
        redis_url="redis://example:6379/0",
        sqlite_path="/data/telegram_alert_bot.sqlite3",
        admin_password="secret",
        global_timeout_minutes=15,
        telegram_api_id=123456,
        telegram_api_hash="hash",
        listener_phone="+10000000000",
        telethon_session_path="/data/listener.session",
    )

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        validate_settings(settings)
