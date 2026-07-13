from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect, migrate
from app.main import create_app
from app.repositories import Repository


def make_settings(tmp_path) -> Settings:
    return Settings(
        telegram_bot_token="",
        webhook_url="https://example.test/webhook",
        redis_url="redis://127.0.0.1:6379/0",
        sqlite_path=str(tmp_path / "app.sqlite3"),
        admin_password="admin-secret",
        global_timeout_minutes=15,
        telegram_api_id=0,
        telegram_api_hash="",
        listener_phone="",
        telethon_session_path="",
        automation_secret="automation-secret",
    )


def make_repo(tmp_path) -> Repository:
    conn = connect(str(tmp_path / "app.sqlite3"))
    migrate(conn)
    return Repository(conn)


def test_automation_command_poll_and_result_round_trip(tmp_path):
    now = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
    repo = make_repo(tmp_path)
    client = TestClient(create_app(repo=repo, settings=make_settings(tmp_path), now_provider=lambda: now))

    create_response = client.post(
        "/api/automation/commands?secret=automation-secret",
        json={"action": "echo", "payload": {"text": "hello"}},
    )
    assert create_response.status_code == 200
    command_id = create_response.json()["command"]["id"]

    poll_response = client.get(
        "/api/automation/poll?secret=automation-secret&worker_id=chrome-1&wait_seconds=0"
    )
    assert poll_response.status_code == 200
    command = poll_response.json()["command"]
    assert command["id"] == command_id
    assert command["status"] == "running"
    assert command["claimed_by"] == "chrome-1"

    result_response = client.post(
        "/api/automation/result?secret=automation-secret",
        json={"id": command_id, "ok": True, "result": {"text": "hello"}},
    )
    assert result_response.status_code == 200
    assert result_response.json()["command"]["status"] == "succeeded"

    status_response = client.get(f"/api/automation/commands/{command_id}?secret=automation-secret")
    assert status_response.status_code == 200
    assert status_response.json()["command"]["result"]["text"] == "hello"


def test_automation_api_rejects_bad_secret(tmp_path):
    repo = make_repo(tmp_path)
    client = TestClient(create_app(repo=repo, settings=make_settings(tmp_path)))

    response = client.get("/api/automation/poll?secret=bad&wait_seconds=0")

    assert response.status_code == 401


def test_expired_automation_command_can_be_reclaimed(tmp_path):
    repo = make_repo(tmp_path)
    now = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
    command = repo.create_automation_command("echo", {"text": "retry"}, now=now)

    first_claim = repo.claim_next_automation_command("chrome-1", now=now, lease_seconds=60)
    second_claim = repo.claim_next_automation_command(
        "chrome-2",
        now=now + timedelta(seconds=61),
        lease_seconds=60,
    )

    assert first_claim["id"] == command["id"]
    assert second_claim["id"] == command["id"]
    assert second_claim["claimed_by"] == "chrome-2"
