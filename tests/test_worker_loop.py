from app.main import create_app
from app.main import should_run_daily_cleanup
from datetime import datetime, timezone


class FakeSettings:
    telegram_bot_token = ""
    webhook_url = ""
    redis_url = "redis://127.0.0.1:6379/0"
    sqlite_path = ":memory:"
    admin_password = "test"
    global_timeout_minutes = 15


def test_app_does_not_start_timeout_worker_without_bot_token():
    app = create_app(repo=object(), queue=object(), settings=FakeSettings())

    assert app.state.timeout_worker_enabled is False


def test_daily_cleanup_runs_once_after_beijing_four_am():
    early = datetime(2026, 6, 13, 19, 30, tzinfo=timezone.utc)
    first_window = datetime(2026, 6, 13, 20, 5, tzinfo=timezone.utc)
    same_day_later = datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)
    next_day = datetime(2026, 6, 14, 20, 1, tzinfo=timezone.utc)

    assert should_run_daily_cleanup(None, early) is False
    assert should_run_daily_cleanup(None, first_window) is True
    assert should_run_daily_cleanup(first_window, same_day_later) is False
    assert should_run_daily_cleanup(first_window, next_day) is True
