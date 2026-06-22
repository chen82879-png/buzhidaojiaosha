import pytest

from app.config import Settings, load_settings, validate_settings


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


def test_load_settings_reads_cs_bot_alert_configuration(monkeypatch):
    monkeypatch.setenv("OTHER_CS_IDS", "123,456")
    monkeypatch.setenv("KEEP_KEYWORDS", "核实中|处理中")
    monkeypatch.setenv("IGNORE_KEYWORDS", "好的,谢谢")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    settings = load_settings()

    assert settings.other_cs_ids == (123, 456)
    assert settings.keep_keywords == ("核实中", "处理中")
    assert settings.ignore_keywords == ("好的", "谢谢")
    assert settings.gemini_api_key == "gemini-key"
    assert settings.gemini_model == "gemini-test"
