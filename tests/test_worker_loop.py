from app.main import create_app


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
