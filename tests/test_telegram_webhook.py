from fastapi.testclient import TestClient

from app.main import create_app


class FakeRepo:
    def __init__(self):
        self.handled = []

    def list_enabled_rules(self):
        return []


class FakeQueue:
    async def close_pending(self, chat_id, message_id):
        pass

    async def add_pending(self, pending, due_at):
        pass


async def capture_handler(message, repo, queue, timeout_minutes, now_timestamp):
    repo.handled.append(message)


def test_webhook_normalizes_telegram_message_update():
    repo = FakeRepo()
    client = TestClient(create_app(repo=repo, queue=FakeQueue(), message_handler=capture_handler))

    response = client.post(
        "/webhook/telegram",
        json={
            "update_id": 1,
            "message": {
                "message_id": 398744,
                "date": 1780588285,
                "chat": {
                    "id": -1001571955528,
                    "title": "Ops Group",
                    "username": "ops_public",
                },
                "from": {
                    "id": 10001,
                    "username": "customer_a",
                },
                "text": "充值失败",
                "reply_to_message": {"message_id": 398700},
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert repo.handled[0].chat_id == "-1001571955528"
    assert repo.handled[0].chat_name == "Ops Group"
    assert repo.handled[0].chat_username == "ops_public"
    assert repo.handled[0].message_id == 398744
    assert repo.handled[0].sender_user_id == 10001
    assert repo.handled[0].sender_username == "customer_a"
    assert repo.handled[0].text == "充值失败"
    assert repo.handled[0].reply_to_message_id == 398700


def test_webhook_ignores_non_message_update():
    repo = FakeRepo()
    client = TestClient(create_app(repo=repo, queue=FakeQueue(), message_handler=capture_handler))

    response = client.post("/webhook/telegram", json={"update_id": 2})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert repo.handled == []
