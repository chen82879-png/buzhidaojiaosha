from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import create_app


def test_mini_redirects_to_tasks_page():
    client = TestClient(create_app())
    response = client.get("/mini", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/mini/tasks"


def test_mini_tasks_page_displays_all_task_sections():
    now = datetime(2026, 6, 13, 12, 45, tzinfo=timezone.utc)

    class Repo:
        def list_open_tasks(self):
            return [
                SimpleNamespace(
                    id=7,
                    status="pending",
                    task_type="wait",
                    keyword="请稍等～yu",
                    chat_name="9-YY-WH2对接",
                    chat_id="-1001",
                    message_excerpt="请稍等～yu，我查一下",
                    message_url="https://t.me/c/1001/50",
                    due_at=now + timedelta(minutes=5),
                ),
                SimpleNamespace(
                    id=8,
                    status="pending",
                    task_type="followup",
                    keyword="请稍等～yu",
                    chat_name="9-YY-WH2对接",
                    chat_id="-1001",
                    message_excerpt="客户又问了一次",
                    message_url="https://t.me/c/1001/70",
                    due_at=now + timedelta(minutes=12),
                ),
                SimpleNamespace(
                    id=9,
                    status="pending",
                    task_type="reply",
                    keyword="客户回复客服",
                    chat_name="9-YY-WH2对接",
                    chat_id="-1001",
                    message_excerpt="客户引用客服消息追问",
                    message_url="https://t.me/c/1001/81",
                    due_at=now + timedelta(minutes=4),
                ),
                SimpleNamespace(
                    id=10,
                    status="pending",
                    task_type="self_reply",
                    keyword="客户连续追问",
                    chat_name="9-YY-WH2对接",
                    chat_id="-1001",
                    message_excerpt="客户又补充了一句",
                    message_url="https://t.me/c/1001/82",
                    due_at=now + timedelta(minutes=3),
                ),
            ]

    client = TestClient(create_app(repo=Repo(), now_provider=lambda: now))
    response = client.get("/mini/tasks")

    assert response.status_code == 200
    assert "任务" in response.text
    assert "稍等 1" in response.text
    assert "跟进 1" in response.text
    assert "漏回 1" in response.text
    assert "自回 1" in response.text
    assert "请稍等～yu" in response.text
    assert "9-YY-WH2对接" in response.text
    assert "剩余 5 分钟" in response.text
    assert "客户又问了一次" in response.text
    assert "剩余 12 分钟" in response.text
    assert "客户引用客服消息追问" in response.text
    assert "客户又补充了一句" in response.text
    assert "mini-tab active" in response.text
    assert "/mini/keywords" in response.text
    assert "/mini/stats" in response.text
    assert "/mini/history" in response.text


def test_mini_tasks_page_shows_empty_states_without_tasks():
    class Repo:
        def list_open_tasks(self):
            return []

    client = TestClient(create_app(repo=Repo()))
    response = client.get("/mini/tasks")

    assert response.status_code == 200
    assert "当前没有稍等任务" in response.text
    assert "当前没有跟进任务" in response.text
    assert "当前没有漏回任务" in response.text
    assert "当前没有自回任务" in response.text


def test_wait_pending_api_keeps_countdown_payload():
    now = datetime(2026, 6, 13, 12, 45, tzinfo=timezone.utc)

    class Repo:
        def list_open_tasks(self):
            return [
                SimpleNamespace(
                    id=8,
                    status="pending",
                    task_type="wait",
                    keyword="请稍等MAD",
                    chat_name="测试群",
                    chat_id="-1002",
                    message_excerpt="请稍等MAD",
                    message_url="https://t.me/c/1002/60",
                    due_at=now + timedelta(minutes=9),
                )
            ]

    client = TestClient(create_app(repo=Repo(), now_provider=lambda: now))
    response = client.get("/api/wait/pending")

    assert response.status_code == 200
    assert response.json()["tasks"][0]["remaining_label"] == "剩余 9 分钟"


def test_mini_keywords_page_uses_three_tab_white_shell():
    client = TestClient(create_app())
    response = client.get("/mini/keywords")

    assert response.status_code == 200
    assert "关键词" in response.text
    assert "请稍等 - AB" in response.text
    assert "请稍等-MAD" in response.text
    assert "保存" in response.text
    assert "接收预警 Chat ID" in response.text
    assert "超时预警" in response.text
    assert "统计" in response.text
    assert "创建任务" in response.text
    assert "stats_enabled::请稍等elk" in response.text
    assert "task_enabled::请稍等elk" in response.text
    assert "alert_enabled::请稍等elk" in response.text
    assert "mini-shell" in response.text
    assert "/mini/tasks" in response.text
    assert "/mini/stats" in response.text
    assert "/mini/history" in response.text


def test_keyword_post_normalizes_alert_to_task_and_keeps_stats_independent():
    class Repo:
        def __init__(self):
            self.saved = []

        def save_keyword_configs(self, configs):
            self.saved = configs

    repo = Repo()
    client = TestClient(create_app(repo=repo))

    response = client.post(
        "/mini/keywords",
        data={
            "stats_enabled::请稍等elk": "1",
            "alert_enabled::请稍等elk": "1",
            "chat_ids::请稍等elk": "10001",
        },
        follow_redirects=False,
    )

    saved = next(config for config in repo.saved if config.keyword == "请稍等elk")
    assert response.status_code == 303
    assert saved.stats_enabled is True
    assert saved.task_enabled is True
    assert saved.alert_enabled is True


def test_keyword_post_allows_statistics_without_task_or_alert():
    class Repo:
        def __init__(self):
            self.saved = []

        def save_keyword_configs(self, configs):
            self.saved = configs

    repo = Repo()
    client = TestClient(create_app(repo=repo))

    client.post(
        "/mini/keywords",
        data={"stats_enabled::请稍等elk": "1"},
        follow_redirects=False,
    )

    saved = next(config for config in repo.saved if config.keyword == "请稍等elk")
    assert saved.stats_enabled is True
    assert saved.task_enabled is False
    assert saved.alert_enabled is False


def test_task_page_shows_severe_alert_due_state():
    now = datetime(2026, 6, 19, 10, 5, tzinfo=timezone.utc)

    class Repo:
        def list_open_tasks(self):
            return [
                SimpleNamespace(
                    id=90,
                    status="alerted",
                    task_type="wait",
                    keyword="请稍等elk",
                    chat_name="Ops",
                    chat_id="-1001",
                    message_excerpt="请稍等elk",
                    message_url="https://t.me/c/1001/90",
                    due_at=datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
                    first_alert_sent_at=datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
                    severe_due_at=datetime(2026, 6, 19, 10, 10, tzinfo=timezone.utc),
                    severe_alert_sent_at=None,
                )
            ]

    response = TestClient(create_app(repo=Repo(), now_provider=lambda: now)).get("/mini/tasks")

    assert response.status_code == 200
    assert "已首次预警" in response.text
    assert "严重预警 18:10" in response.text


def test_mini_keywords_page_hides_configured_groups():
    class Repo:
        def list_enabled_chat_summaries(self):
            return [
                {"chat_name": "9-YY-DL对接", "chat_id": "-1001571955528"},
            ]

        def keyword_hit_counts(self):
            return []

    client = TestClient(create_app(repo=Repo()))
    response = client.get("/mini/keywords")

    assert response.status_code == 200
    assert "启用群组" not in response.text
    assert "9-YY-DL对接" not in response.text
    assert "-1001571955528" not in response.text


def test_mini_stats_page_displays_keyword_statistics_and_audit():
    class Repo:
        def keyword_statistics(self, now=None):
            return [
                {
                    "keyword": "请稍等～yu",
                    "enabled": True,
                    "recipient_chat_ids": "5317794797",
                    "today_count": 35,
                    "seven_day_count": 42,
                    "total_count": 88,
                    "latest_time": "2026-06-13T12:44:06+00:00",
                    "latest_chat_name": "9-YY-WH2对接",
                    "latest_message_url": "https://t.me/c/1001/50",
                }
            ]

        def list_open_tasks(self):
            return [SimpleNamespace(task_type="wait")]

        def recent_audit_records(self, limit=5):
            return [
                {
                    "matched_keyword": "请稍等～yu",
                    "chat_name": "9-YY-WH2对接",
                    "message_excerpt": "请稍等～yu，我查一下",
                    "created_at": "2026-06-13T12:44:06+00:00",
                    "message_url": "https://t.me/c/1001/50",
                }
            ]

    client = TestClient(create_app(repo=Repo()))
    response = client.get("/mini/stats")

    assert response.status_code == 200
    assert "统计" in response.text
    assert "今日命中" in response.text
    assert "35" in response.text
    assert "待处理任务" in response.text
    assert "/mini/history" in response.text
    assert "历史检测" in response.text
    assert "今日闭环" not in response.text
    assert "今日异常" not in response.text
    assert "最近审计" in response.text
    assert "请稍等～yu，我查一下" in response.text


def test_mini_history_page_displays_closed_loop_and_anomalies():
    class Repo:
        def history_check_summary(self, limit=20, now=None):
            return {
                "scope_label": "2026-06-13 北京时间",
                "closed_loop": {
                    "total": 3,
                    "completed": 2,
                    "pending": 1,
                    "alerted": 0,
                    "deleted": 0,
                    "duplicate": 0,
                    "completion_rate": 67,
                },
                "anomaly_counts": [{"key": "reply", "label": "漏回", "count": 1}],
                "anomaly_items": [
                    {
                        "id": 7,
                        "key": "reply",
                        "label": "漏回",
                        "task_type": "reply",
                        "status": "pending",
                        "keyword": "请稍等～yu",
                        "chat_name": "9-YY-WH2对接",
                        "started_at": "2026-06-13T12:44:06+00:00",
                        "message_excerpt": "客户引用客服消息追问",
                        "message_url": "https://t.me/c/1001/50",
                    }
                ],
                "counts": [{"task_type": "wait", "status": "pending", "count": 1}],
                "open_items": [],
            }

    client = TestClient(create_app(repo=Repo()))
    response = client.get("/mini/history")

    assert response.status_code == 200
    assert "历史检测" in response.text
    assert "今日闭环" in response.text
    assert "今日异常" in response.text
    assert "闭环率" in response.text
    assert "67%" in response.text
    assert "漏回：" in response.text
    assert "客户引用客服消息追问" in response.text
    assert "mini-tab active" in response.text


def test_history_check_api_returns_summary():
    class Repo:
        def history_check_summary(self, limit=20, now=None):
            return {
                "date": "2026-06-13",
                "closed_loop": {"total": 1, "completed": 0, "completion_rate": 0},
                "anomaly_counts": [{"key": "reply", "label": "漏回", "count": 2}],
                "anomaly_items": [],
                "counts": [{"task_type": "reply", "status": "pending", "count": 2}],
                "open_items": [],
            }

    client = TestClient(create_app(repo=Repo()))
    response = client.get("/api/history/check")

    assert response.status_code == 200
    assert response.json()["summary"]["anomaly_counts"][0]["label"] == "漏回"


def test_config_status_api_returns_safe_configuration_summary():
    class Repo:
        def list_open_tasks(self):
            return []

        def list_keyword_configs(self):
            return []

        def enabled_chat_count(self):
            return 2

        def list_enabled_chat_summaries(self):
            return [
                {"chat_name": "群 A", "chat_id": "-1001"},
                {"chat_name": "群 B", "chat_id": "-1002"},
            ]

    client = TestClient(create_app(repo=Repo()))
    response = client.get("/api/config/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled_chat_count"] == 2
    assert payload["enabled_chats"][0]["chat_name"] == "群 A"
    assert "telegram_bot_token" not in str(payload).lower()
    assert "telegram_api_hash" not in str(payload).lower()
    assert "listener_phone" not in str(payload).lower()
