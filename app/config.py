import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    webhook_url: str
    redis_url: str
    sqlite_path: str
    admin_password: str
    global_timeout_minutes: int
    telegram_api_id: int
    telegram_api_hash: str
    listener_phone: str
    telethon_session_path: str
    automation_secret: str = ""


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        webhook_url=os.getenv("WEBHOOK_URL", ""),
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        sqlite_path=os.getenv("SQLITE_PATH", "./data/telegram_alert_bot.sqlite3"),
        admin_password=os.getenv("ADMIN_PASSWORD", "change-me"),
        global_timeout_minutes=int(os.getenv("GLOBAL_TIMEOUT_MINUTES", "15")),
        telegram_api_id=int(os.getenv("TELEGRAM_API_ID", "0")),
        telegram_api_hash=os.getenv("TELEGRAM_API_HASH", ""),
        listener_phone=os.getenv("LISTENER_PHONE", ""),
        telethon_session_path=os.getenv("TELETHON_SESSION_PATH", "./data/listener.session"),
        automation_secret=os.getenv("AUTOMATION_SECRET", os.getenv("ADMIN_PASSWORD", "change-me")),
    )


def validate_settings(settings: Settings) -> None:
    required = {
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
        "WEBHOOK_URL": settings.webhook_url,
        "REDIS_URL": settings.redis_url,
        "SQLITE_PATH": settings.sqlite_path,
        "ADMIN_PASSWORD": settings.admin_password,
        "TELEGRAM_API_ID": settings.telegram_api_id,
        "TELEGRAM_API_HASH": settings.telegram_api_hash,
        "LISTENER_PHONE": settings.listener_phone,
        "TELETHON_SESSION_PATH": settings.telethon_session_path,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("Missing required settings: " + ", ".join(missing))
    if settings.global_timeout_minutes <= 0:
        raise ValueError("GLOBAL_TIMEOUT_MINUTES must be greater than 0")
