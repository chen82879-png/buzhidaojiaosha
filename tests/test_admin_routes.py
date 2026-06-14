from fastapi.testclient import TestClient

from types import SimpleNamespace

from app.main import create_app


def test_root_redirects_to_mini_tasks():
    client = TestClient(create_app())
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/mini/tasks"


def test_old_admin_stats_page_redirects_to_status_panel():
    client = TestClient(create_app())
    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/mini/tasks"


def test_telegram_webhook_accepts_empty_payload():
    client = TestClient(create_app())
    response = client.post("/webhook/telegram", json={})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_admin_rules_page_redirects_to_fixed_keywords():
    client = TestClient(create_app())
    response = client.get("/admin/rules", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/mini/keywords"


def test_admin_alerts_page_redirects_to_status_panel():
    client = TestClient(create_app())
    response = client.get("/admin/alerts", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/mini/stats"


def test_admin_fixed_keywords_page_loads():
    client = TestClient(create_app())
    response = client.get("/admin/keywords", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/mini/keywords"


def test_wait_pending_api_returns_open_tasks():
    class Repo:
        def list_open_tasks(self):
            return [
                SimpleNamespace(
                    id=7,
                    task_type="wait",
                    status="pending",
                    keyword="请稍等",
                    chat_id="-1001",
                    chat_name="测试群",
                    message_excerpt="请稍等，我查一下",
                    message_url="https://t.me/c/1001/10",
                    due_at="2026-06-13T10:00:00+00:00",
                )
            ]

    client = TestClient(create_app(repo=Repo()))
    response = client.get("/api/wait/pending")

    assert response.status_code == 200
    assert response.json()["tasks"][0]["id"] == 7
    assert response.json()["tasks"][0]["chat_name"] == "测试群"


def test_audit_recent_api_returns_empty_list_without_repository_support():
    client = TestClient(create_app(repo=object(), queue=object()))
    response = client.get("/api/audit/recent")

    assert response.status_code == 200
    assert response.json() == {"records": []}
