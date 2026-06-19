from datetime import datetime, timedelta, timezone

from app.db import connect, migrate
from app.models import KeywordConfig
from app.repositories import Repository


def test_migrate_creates_rule_keyword_staff_and_hit_records(tmp_path):
    db_path = tmp_path / "app.sqlite3"
    conn = connect(str(db_path))
    migrate(conn)
    repo = Repository(conn)

    rule_id = repo.create_monitor_rule(chat_id="-1001571955528", chat_name="Ops Group", enabled=True)
    repo.add_keyword(rule_id=rule_id, keyword="充值", enabled=True, note="payment")
    repo.add_staff(
        rule_id=rule_id,
        telegram_user_id=9001,
        telegram_username="ML_YYZB3",
        display_name="YY_6/9_值班号3",
        enabled=True,
    )
    repo.record_keyword_hit(
        rule_id=rule_id,
        chat_id="-1001571955528",
        chat_name="Ops Group",
        message_id=398744,
        telegram_user_id=10001,
        telegram_username="customer_a",
        matched_keyword="充值",
        message_excerpt="充值失败",
        message_url="https://t.me/c/1571955528/398744",
        message_time=datetime(2026, 6, 4, 21, 11, 25, tzinfo=timezone.utc),
    )

    rules = repo.list_enabled_rules()
    stats = repo.keyword_hit_counts()

    assert rules[0].chat_id == "-1001571955528"
    assert rules[0].keywords[0].keyword == "充值"
    assert rules[0].staff[0].telegram_username == "ML_YYZB3"
    assert stats[0]["matched_keyword"] == "充值"
    assert stats[0]["count"] == 1


def test_keyword_rollup_preserves_seven_day_stats_after_detail_cleanup(tmp_path):
    db_path = tmp_path / "app.sqlite3"
    conn = connect(str(db_path))
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id="-1001571955528", chat_name="Ops Group", enabled=True)
    repo.save_keyword_configs([KeywordConfig(keyword="请稍等elk", enabled=True, recipient_chat_ids=[7511822833])])
    now = datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)
    for offset, message_id in [(1, 101), (4, 104)]:
        repo.record_keyword_hit(
            rule_id=rule_id,
            chat_id="-1001571955528",
            chat_name="Ops Group",
            message_id=message_id,
            telegram_user_id=7511822833,
            telegram_username="elk",
            matched_keyword="请稍等elk",
            message_excerpt="请稍等elk",
            message_url=f"https://t.me/c/1571955528/{message_id}",
            message_time=now - timedelta(days=offset),
        )

    repo.rollup_keyword_hits(before=now)
    repo.cleanup_old_details(now=now, detail_retention_days=3, rollup_retention_days=30)
    stats = {row["keyword"]: row for row in repo.keyword_statistics(now=now)}
    detail_count = conn.execute("SELECT COUNT(*) AS count FROM keyword_hits").fetchone()["count"]

    assert detail_count == 1
    assert stats["请稍等elk"]["seven_day_count"] == 2
    assert stats["请稍等elk"]["today_count"] == 0
    assert stats["请稍等elk"]["latest_message_url"] == "https://t.me/c/1571955528/101"


def test_keyword_statistics_enabled_is_independent_from_alert_recipients(tmp_path):
    db_path = tmp_path / "app.sqlite3"
    conn = connect(str(db_path))
    migrate(conn)
    repo = Repository(conn)

    repo.save_keyword_configs([KeywordConfig(keyword="请稍等elk", enabled=True, recipient_chat_ids=[])])

    stats = {row["keyword"]: row for row in repo.keyword_statistics(now=datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc))}

    assert stats["请稍等elk"]["enabled"] is True
    assert stats["请稍等elk"]["recipient_chat_ids"] == ""


def test_keyword_statistics_today_uses_beijing_calendar_day(tmp_path):
    db_path = tmp_path / "app.sqlite3"
    conn = connect(str(db_path))
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id="-1001571955528", chat_name="Ops Group", enabled=True)
    repo.save_keyword_configs([KeywordConfig(keyword="请稍等elk", enabled=True, recipient_chat_ids=[])])

    repo.record_keyword_hit(
        rule_id=rule_id,
        chat_id="-1001571955528",
        chat_name="Ops Group",
        message_id=200,
        telegram_user_id=7511822833,
        telegram_username="elk",
        matched_keyword="请稍等elk",
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1571955528/200",
        message_time=datetime(2026, 6, 13, 15, 50, tzinfo=timezone.utc),
    )
    repo.record_keyword_hit(
        rule_id=rule_id,
        chat_id="-1001571955528",
        chat_name="Ops Group",
        message_id=201,
        telegram_user_id=7511822833,
        telegram_username="elk",
        matched_keyword="请稍等elk",
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1571955528/201",
        message_time=datetime(2026, 6, 13, 16, 10, tzinfo=timezone.utc),
    )

    stats = {row["keyword"]: row for row in repo.keyword_statistics(now=datetime(2026, 6, 13, 16, 30, tzinfo=timezone.utc))}

    assert stats["请稍等elk"]["today_count"] == 1


def test_keyword_statistics_excludes_deleted_wait_tasks(tmp_path):
    db_path = tmp_path / "app.sqlite3"
    conn = connect(str(db_path))
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id="-1001", chat_name="Ops", enabled=True)
    repo.save_keyword_configs([KeywordConfig(keyword="请稍等elk", enabled=True, recipient_chat_ids=[])])
    message_time = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    repo.record_keyword_hit(
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        message_id=50,
        telegram_user_id=7511822833,
        telegram_username="elk",
        matched_keyword="请稍等elk",
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1001/50",
        message_time=message_time,
    )
    task = repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=50,
        wait_message_id=50,
        trigger_message_id=50,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1001/50",
        recipient_chat_ids=[],
        started_at=message_time,
        due_at=message_time + timedelta(minutes=8),
    )
    repo.mark_task_deleted(task.id)

    stats = {row["keyword"]: row for row in repo.keyword_statistics(now=message_time)}

    assert stats["请稍等elk"]["today_count"] == 0
    assert stats["请稍等elk"]["seven_day_count"] == 0
    assert stats["请稍等elk"]["total_count"] == 0


def test_marks_stale_overdue_pending_tasks_alerted(tmp_path):
    db_path = tmp_path / "app.sqlite3"
    conn = connect(str(db_path))
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id="-1001", chat_name="Ops", enabled=True)
    now = datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)
    task = repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=40,
        wait_message_id=50,
        trigger_message_id=50,
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1001/50",
        recipient_chat_ids=[7511822833],
        started_at=now - timedelta(minutes=20),
        due_at=now - timedelta(minutes=10),
    )

    repo.mark_stale_overdue_tasks_alerted(now=now, grace_minutes=2)

    assert repo.get_monitor_task(task.id).status == "alerted"
    assert repo.list_open_tasks() == []


def test_recipient_display_ignores_test_staff_placeholder_when_recent_username_exists(tmp_path):
    db_path = tmp_path / "app.sqlite3"
    conn = connect(str(db_path))
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id="-1001", chat_name="Ops", enabled=True)
    repo.add_staff(
        rule_id=rule_id,
        telegram_user_id=7511822833,
        telegram_username="",
        display_name="test-staff",
        enabled=True,
    )
    repo.record_keyword_hit(
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        message_id=825085,
        telegram_user_id=7511822833,
        telegram_username="Y_YY_GRYBUGES",
        matched_keyword="请稍等elk",
        message_excerpt="请稍等elk",
        message_url="https://t.me/c/1001/825085",
        message_time=datetime(2026, 6, 9, 15, 39, 28, tzinfo=timezone.utc),
    )

    display = repo.recipient_display_for_user(7511822833)

    assert display == {
        "display_name": "Y_YY_GRYBUGES",
        "telegram_username": "Y_YY_GRYBUGES",
    }


def test_history_check_summary_reports_today_closed_loop_and_anomalies(tmp_path):
    db_path = tmp_path / "app.sqlite3"
    conn = connect(str(db_path))
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id="-1001", chat_name="Ops", enabled=True)
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)

    completed = repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=100,
        wait_message_id=101,
        trigger_message_id=101,
        message_excerpt="请稍等elk 已完成",
        message_url="https://t.me/c/1001/101",
        recipient_chat_ids=[],
        started_at=datetime(2026, 6, 13, 1, 0, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 13, 1, 8, tzinfo=timezone.utc),
    )
    repo.complete_tasks_referencing("-1001", 101, datetime(2026, 6, 13, 1, 5, tzinfo=timezone.utc))
    repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=110,
        wait_message_id=111,
        trigger_message_id=111,
        message_excerpt="请稍等elk 待处理",
        message_url="https://t.me/c/1001/111",
        recipient_chat_ids=[],
        started_at=datetime(2026, 6, 13, 2, 0, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 13, 2, 8, tzinfo=timezone.utc),
    )
    alerted = repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=120,
        wait_message_id=121,
        trigger_message_id=121,
        message_excerpt="请稍等elk 超时",
        message_url="https://t.me/c/1001/121",
        recipient_chat_ids=[],
        started_at=datetime(2026, 6, 13, 3, 0, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 13, 3, 8, tzinfo=timezone.utc),
    )
    repo.mark_task_alerted(alerted.id, datetime(2026, 6, 13, 3, 9, tzinfo=timezone.utc))
    duplicate = repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=130,
        wait_message_id=131,
        trigger_message_id=131,
        message_excerpt="请稍等elk 重复",
        message_url="https://t.me/c/1001/131",
        recipient_chat_ids=[],
        started_at=datetime(2026, 6, 13, 4, 0, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 13, 4, 8, tzinfo=timezone.utc),
        status="duplicate",
    )
    followup = repo.create_monitor_task(
        task_type="followup",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=20001,
        staff_username="customer",
        root_message_id=140,
        wait_message_id=141,
        trigger_message_id=142,
        message_excerpt="客户跟进",
        message_url="https://t.me/c/1001/142",
        recipient_chat_ids=[],
        started_at=datetime(2026, 6, 13, 5, 0, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 13, 5, 15, tzinfo=timezone.utc),
    )
    repo.create_monitor_task(
        task_type="reply",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=20002,
        staff_username="customer2",
        root_message_id=150,
        wait_message_id=151,
        trigger_message_id=152,
        message_excerpt="客户漏回",
        message_url="https://t.me/c/1001/152",
        recipient_chat_ids=[],
        started_at=datetime(2026, 6, 13, 6, 0, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 13, 6, 5, tzinfo=timezone.utc),
    )
    repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=90,
        wait_message_id=91,
        trigger_message_id=91,
        message_excerpt="北京时间昨天",
        message_url="https://t.me/c/1001/91",
        recipient_chat_ids=[],
        started_at=datetime(2026, 6, 12, 15, 50, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 12, 15, 58, tzinfo=timezone.utc),
    )
    deleted_wait = repo.create_monitor_task(
        task_type="wait",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=7511822833,
        staff_username="elk",
        root_message_id=160,
        wait_message_id=161,
        trigger_message_id=161,
        message_excerpt="已删除稍等",
        message_url="https://t.me/c/1001/161",
        recipient_chat_ids=[],
        started_at=datetime(2026, 6, 13, 7, 0, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 13, 7, 8, tzinfo=timezone.utc),
    )
    repo.mark_task_deleted(deleted_wait.id)
    deleted_reply = repo.create_monitor_task(
        task_type="reply",
        rule_id=rule_id,
        chat_id="-1001",
        chat_name="Ops",
        keyword="请稍等elk",
        staff_user_id=20003,
        staff_username="customer3",
        root_message_id=170,
        wait_message_id=171,
        trigger_message_id=172,
        message_excerpt="已删除漏回",
        message_url="https://t.me/c/1001/172",
        recipient_chat_ids=[],
        started_at=datetime(2026, 6, 13, 8, 0, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 13, 8, 5, tzinfo=timezone.utc),
    )
    repo.mark_task_deleted(deleted_reply.id)

    summary = repo.history_check_summary(now=now, limit=10)

    assert summary["date"] == "2026-06-13"
    assert summary["closed_loop"] == {
        "total": 4,
        "completed": 1,
        "pending": 1,
        "alerted": 1,
        "deleted": 0,
        "duplicate": 1,
        "completion_rate": 25,
    }
    anomaly_counts = {row["key"]: row["count"] for row in summary["anomaly_counts"]}
    assert anomaly_counts["alerted"] == 1
    assert anomaly_counts["duplicate"] == 1
    assert anomaly_counts["followup"] == 1
    assert anomaly_counts["reply"] == 1
    assert "deleted" not in anomaly_counts
    assert {item["id"] for item in summary["anomaly_items"]} >= {alerted.id, duplicate.id, followup.id}
    assert completed.id not in {item["id"] for item in summary["anomaly_items"]}
    assert deleted_wait.id not in {item["id"] for item in summary["anomaly_items"]}
    assert deleted_reply.id not in {item["id"] for item in summary["anomaly_items"]}


def test_migrate_adds_keyword_layers_and_severe_alert_fields(tmp_path):
    conn = connect(str(tmp_path / "app.sqlite3"))
    migrate(conn)

    keyword_columns = {row["name"] for row in conn.execute("PRAGMA table_info(keyword_configs)")}
    task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(monitor_tasks)")}

    assert {"stats_enabled", "task_enabled", "alert_enabled"} <= keyword_columns
    assert {"first_alert_sent_at", "severe_due_at", "severe_alert_sent_at"} <= task_columns


def test_existing_enabled_keyword_defaults_all_layers_on(tmp_path):
    conn = connect(str(tmp_path / "app.sqlite3"))
    migrate(conn)
    repo = Repository(conn)
    repo.save_keyword_configs(
        [KeywordConfig(keyword="请稍等elk", enabled=True, recipient_chat_ids=[10001])]
    )

    config = next(item for item in repo.list_keyword_configs() if item.keyword == "请稍等elk")

    assert config.stats_enabled is True
    assert config.task_enabled is True
    assert config.alert_enabled is True


def test_first_alert_schedules_one_severe_alert_and_can_be_completed(tmp_path):
    conn = connect(str(tmp_path / "app.sqlite3"))
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id="-1001", chat_name="Ops", enabled=True)
    task = repo.create_monitor_task(
        task_type="wait", rule_id=rule_id, chat_id="-1001", chat_name="Ops",
        keyword="请稍等elk", staff_user_id=10001, staff_username="elk",
        root_message_id=40, wait_message_id=50, trigger_message_id=50,
        message_excerpt="请稍等elk", message_url="https://t.me/c/1001/50",
        recipient_chat_ids=[10001],
        started_at=datetime(2026, 6, 19, 9, 52, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
    )
    first_alert_at = datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc)
    severe_due_at = first_alert_at + timedelta(minutes=10)

    repo.mark_first_alert_sent(task.id, first_alert_at, severe_due_at)

    alerted = repo.get_monitor_task(task.id)
    assert alerted.status == "alerted"
    assert alerted.first_alert_sent_at == first_alert_at
    assert alerted.severe_due_at == severe_due_at
    assert repo.list_due_severe_tasks(severe_due_at) == [alerted]
    completed = repo.complete_tasks_referencing(
        "-1001", 50, datetime(2026, 6, 19, 10, 5, tzinfo=timezone.utc)
    )
    assert completed[0].id == task.id
    assert repo.list_due_severe_tasks(severe_due_at) == []


def test_mark_severe_alert_sent_is_idempotent(tmp_path):
    conn = connect(str(tmp_path / "app.sqlite3"))
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id="-1001", chat_name="Ops", enabled=True)
    task = repo.create_monitor_task(
        task_type="reply", rule_id=rule_id, chat_id="-1001", chat_name="Ops",
        keyword="漏回", staff_user_id=20001, staff_username="customer",
        root_message_id=70, wait_message_id=70, trigger_message_id=70,
        message_excerpt="查询", message_url="https://t.me/c/1001/70",
        recipient_chat_ids=[10001],
        started_at=datetime(2026, 6, 19, 9, 55, tzinfo=timezone.utc),
        due_at=datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
    )
    repo.mark_first_alert_sent(
        task.id,
        datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 6, 19, 10, 10, tzinfo=timezone.utc),
    )
    first = datetime(2026, 6, 19, 10, 10, tzinfo=timezone.utc)
    second = datetime(2026, 6, 19, 10, 11, tzinfo=timezone.utc)

    repo.mark_severe_alert_sent(task.id, first)
    repo.mark_severe_alert_sent(task.id, second)

    assert repo.get_monitor_task(task.id).severe_alert_sent_at == first
