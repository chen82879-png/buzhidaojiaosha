import sqlite3
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.fixed_keywords import FIXED_KEYWORDS
from app.models import KeywordConfig, MessageSnapshot, MonitorRule, MonitorTask, RuleKeyword, RuleStaff

DISPLAY_TZ = ZoneInfo("Asia/Shanghai")
ANOMALY_LABELS = {
    "alerted": "超时预警",
    "deleted": "已删除",
    "duplicate": "重复稍等",
    "followup": "跟进",
    "reply": "漏回",
    "self_reply": "自回",
}


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_monitor_rule(self, chat_id: str, chat_name: str, enabled: bool) -> int:
        cur = self.conn.execute(
            "INSERT INTO monitor_rules(chat_id, chat_name, enabled) VALUES (?, ?, ?)",
            (chat_id, chat_name, int(enabled)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_keyword(self, rule_id: int, keyword: str, enabled: bool, note: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO rule_keywords(rule_id, keyword, enabled, note) VALUES (?, ?, ?, ?)",
            (rule_id, keyword, int(enabled), note),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_staff(
        self,
        rule_id: int,
        telegram_user_id: int,
        telegram_username: str,
        display_name: str,
        enabled: bool,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO rule_staff(rule_id, telegram_user_id, telegram_username, display_name, enabled)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rule_id, telegram_user_id, telegram_username, display_name, int(enabled)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_enabled_rules(self) -> list[MonitorRule]:
        rule_rows = self.conn.execute(
            "SELECT id, chat_id, chat_name, enabled FROM monitor_rules WHERE enabled = 1 ORDER BY id"
        ).fetchall()
        rules: list[MonitorRule] = []
        for row in rule_rows:
            keyword_rows = self.conn.execute(
                "SELECT id, rule_id, keyword, enabled, note FROM rule_keywords WHERE rule_id = ? ORDER BY id",
                (row["id"],),
            ).fetchall()
            staff_rows = self.conn.execute(
                """
                SELECT id, rule_id, telegram_user_id, telegram_username, display_name, enabled
                FROM rule_staff WHERE rule_id = ? ORDER BY id
                """,
                (row["id"],),
            ).fetchall()
            rules.append(
                MonitorRule(
                    id=row["id"],
                    chat_id=row["chat_id"],
                    chat_name=row["chat_name"],
                    enabled=bool(row["enabled"]),
                    keywords=[
                        RuleKeyword(
                            id=k["id"],
                            rule_id=k["rule_id"],
                            keyword=k["keyword"],
                            enabled=bool(k["enabled"]),
                            note=k["note"],
                        )
                        for k in keyword_rows
                    ],
                    staff=[
                        RuleStaff(
                            id=s["id"],
                            rule_id=s["rule_id"],
                            telegram_user_id=s["telegram_user_id"],
                            telegram_username=s["telegram_username"],
                            display_name=s["display_name"],
                            enabled=bool(s["enabled"]),
                        )
                        for s in staff_rows
                    ],
                )
            )
        return rules

    def record_keyword_hit(
        self,
        rule_id: int,
        chat_id: str,
        chat_name: str,
        message_id: int,
        telegram_user_id: int,
        telegram_username: str,
        matched_keyword: str,
        message_excerpt: str,
        message_url: str,
        message_time: datetime,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO keyword_hits(
                rule_id, chat_id, chat_name, message_id, telegram_user_id, telegram_username,
                matched_keyword, message_excerpt, message_url, message_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                chat_id,
                chat_name,
                message_id,
                telegram_user_id,
                telegram_username,
                matched_keyword,
                message_excerpt,
                message_url,
                message_time.isoformat(),
            ),
        )
        self.conn.commit()

    def keyword_hit_counts(self) -> list[dict[str, object]]:
        rows = self.conn.execute(
            """
            SELECT kh.matched_keyword, COUNT(*) AS count
            FROM keyword_hits kh
            WHERE NOT EXISTS (
                SELECT 1
                FROM monitor_tasks mt
                WHERE mt.chat_id = kh.chat_id
                  AND mt.wait_message_id = kh.message_id
                  AND mt.task_type = 'wait'
                  AND mt.status = 'deleted'
            )
            GROUP BY kh.matched_keyword
            ORDER BY count DESC, matched_keyword
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def recent_audit_records(self, limit: int = 50) -> list[dict[str, object]]:
        rows = self.conn.execute(
            """
            SELECT
                id,
                'keyword_hit' AS event_type,
                chat_id,
                chat_name,
                message_id,
                telegram_user_id,
                telegram_username,
                matched_keyword,
                message_excerpt,
                message_url,
                message_time,
                created_at
            FROM keyword_hits
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def rollup_keyword_hits(self, before: datetime) -> None:
        rows = self.conn.execute(
            """
            SELECT
                date(datetime(kh.message_time), '+8 hours') AS stat_date,
                kh.matched_keyword,
                kh.chat_id,
                kh.chat_name,
                kh.telegram_user_id,
                COUNT(*) AS count
            FROM keyword_hits kh
            WHERE datetime(kh.message_time) < datetime(?)
              AND NOT EXISTS (
                SELECT 1
                FROM monitor_tasks mt
                WHERE mt.chat_id = kh.chat_id
                  AND mt.wait_message_id = kh.message_id
                  AND mt.task_type = 'wait'
                  AND mt.status = 'deleted'
              )
            GROUP BY stat_date, kh.matched_keyword, kh.chat_id, kh.chat_name, kh.telegram_user_id
            """,
            (before.isoformat(),),
        ).fetchall()
        for row in rows:
            self.conn.execute(
                """
                INSERT INTO keyword_daily_stats(
                    stat_date, matched_keyword, chat_id, chat_name, telegram_user_id, count
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(stat_date, matched_keyword, chat_id, telegram_user_id)
                DO UPDATE SET
                    chat_name = excluded.chat_name,
                    count = excluded.count
                """,
                (
                    row["stat_date"],
                    row["matched_keyword"],
                    row["chat_id"],
                    row["chat_name"],
                    row["telegram_user_id"],
                    row["count"],
                ),
            )
        self.conn.commit()

    def cleanup_old_details(
        self,
        now: datetime,
        detail_retention_days: int = 3,
        rollup_retention_days: int = 30,
    ) -> None:
        detail_cutoff = now - timedelta(days=detail_retention_days)
        rollup_cutoff = (now - timedelta(days=rollup_retention_days)).date().isoformat()
        self.conn.execute(
            "DELETE FROM keyword_hits WHERE datetime(message_time) < datetime(?)",
            (detail_cutoff.isoformat(),),
        )
        self.conn.execute(
            """
            DELETE FROM monitor_tasks
            WHERE status IN ('completed', 'deleted', 'alerted')
              AND datetime(created_at) < datetime(?)
            """,
            (detail_cutoff.isoformat(),),
        )
        self.conn.execute(
            "DELETE FROM keyword_daily_stats WHERE stat_date < ?",
            (rollup_cutoff,),
        )
        self.conn.commit()

    def keyword_statistics(self, now: datetime | None = None) -> list[dict[str, object]]:
        now = now or datetime.now().astimezone()
        local_now = now.astimezone(DISPLAY_TZ) if now.tzinfo else now.replace(tzinfo=DISPLAY_TZ)
        today = local_now.date().isoformat()
        seven_day_start = (local_now - timedelta(days=7)).date().isoformat()
        detail_cutoff_date = (local_now - timedelta(days=3)).date().isoformat()
        rollup_rows = self.conn.execute(
            """
            SELECT
                matched_keyword,
                SUM(count) AS total_count,
                SUM(CASE WHEN stat_date = ? THEN count ELSE 0 END) AS today_count,
                SUM(CASE WHEN stat_date >= ? THEN count ELSE 0 END) AS seven_day_count
            FROM keyword_daily_stats
            WHERE stat_date < ?
            GROUP BY matched_keyword
            """,
            (today, seven_day_start, detail_cutoff_date),
        ).fetchall()
        by_keyword = {row["matched_keyword"]: dict(row) for row in rollup_rows}
        configs = {config.keyword: config for config in self.list_keyword_configs()}
        stats: list[dict[str, object]] = []
        for keyword in FIXED_KEYWORDS:
            row = by_keyword.get(keyword, {})
            detail = self.conn.execute(
                """
                SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN date(datetime(kh.message_time), '+8 hours') = ? THEN 1 ELSE 0 END) AS today_count,
                    SUM(CASE WHEN date(datetime(kh.message_time), '+8 hours') >= ? THEN 1 ELSE 0 END) AS seven_day_count
                FROM keyword_hits kh
                WHERE kh.matched_keyword = ?
                  AND NOT EXISTS (
                    SELECT 1
                    FROM monitor_tasks mt
                    WHERE mt.chat_id = kh.chat_id
                      AND mt.wait_message_id = kh.message_id
                      AND mt.task_type = 'wait'
                      AND mt.status = 'deleted'
                  )
                """,
                (today, seven_day_start, keyword),
            ).fetchone()
            latest = self.conn.execute(
                """
                SELECT kh.chat_name, kh.message_url, kh.message_time
                FROM keyword_hits kh
                WHERE kh.matched_keyword = ?
                  AND NOT EXISTS (
                    SELECT 1
                    FROM monitor_tasks mt
                    WHERE mt.chat_id = kh.chat_id
                      AND mt.wait_message_id = kh.message_id
                      AND mt.task_type = 'wait'
                      AND mt.status = 'deleted'
                  )
                ORDER BY kh.message_time DESC, kh.id DESC
                LIMIT 1
                """,
                (keyword,),
            ).fetchone()
            config = configs[keyword]
            stats.append(
                {
                    "keyword": keyword,
                    "enabled": config.enabled,
                    "recipient_chat_ids": ", ".join(str(chat_id) for chat_id in config.recipient_chat_ids),
                    "today_count": int(row.get("today_count") or 0) + int(detail["today_count"] or 0),
                    "seven_day_count": int(row.get("seven_day_count") or 0) + int(detail["seven_day_count"] or 0),
                    "total_count": int(row.get("total_count") or 0) + int(detail["total_count"] or 0),
                    "latest_time": latest["message_time"] if latest else "",
                    "latest_chat_name": latest["chat_name"] if latest else "",
                    "latest_message_url": latest["message_url"] if latest else "",
                }
            )
        return stats

    @staticmethod
    def _parse_chat_ids(value: str) -> list[int]:
        if not value:
            return []
        try:
            raw_values = json.loads(value)
        except json.JSONDecodeError:
            raw_values = [part.strip() for part in value.split(",")]
        chat_ids: list[int] = []
        for raw in raw_values:
            text = str(raw).strip()
            if text:
                chat_ids.append(int(text))
        return chat_ids

    @staticmethod
    def _dump_chat_ids(chat_ids: list[int]) -> str:
        return json.dumps(chat_ids, ensure_ascii=False)

    def list_keyword_configs(self) -> list[KeywordConfig]:
        rows = self.conn.execute(
            """
            SELECT keyword, enabled, stats_enabled, task_enabled, alert_enabled, recipient_chat_ids
            FROM keyword_configs
            """
        ).fetchall()
        by_keyword = {row["keyword"]: row for row in rows}
        configs: list[KeywordConfig] = []
        for keyword in FIXED_KEYWORDS:
            row = by_keyword.get(keyword)
            if row is None:
                configs.append(
                    KeywordConfig(
                        keyword=keyword,
                        enabled=False,
                        recipient_chat_ids=[],
                        stats_enabled=False,
                        task_enabled=False,
                        alert_enabled=False,
                    )
                )
            else:
                configs.append(
                    KeywordConfig(
                        keyword=keyword,
                        enabled=bool(row["enabled"]),
                        recipient_chat_ids=self._parse_chat_ids(row["recipient_chat_ids"]),
                        alert_enabled=bool(row["alert_enabled"]),
                        stats_enabled=bool(row["stats_enabled"]),
                        task_enabled=bool(row["task_enabled"]),
                    )
                )
        return configs

    def save_keyword_configs(self, configs: list[KeywordConfig]) -> None:
        for config in configs:
            task_enabled = bool(config.task_enabled)
            alert_enabled = bool(config.alert_enabled and task_enabled)
            self.conn.execute(
                """
                INSERT INTO keyword_configs(
                    keyword, enabled, stats_enabled, task_enabled, alert_enabled,
                    recipient_chat_ids, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(keyword) DO UPDATE SET
                    enabled = excluded.enabled,
                    stats_enabled = excluded.stats_enabled,
                    task_enabled = excluded.task_enabled,
                    alert_enabled = excluded.alert_enabled,
                    recipient_chat_ids = excluded.recipient_chat_ids,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    config.keyword,
                    int(config.enabled),
                    int(config.stats_enabled),
                    int(task_enabled),
                    int(alert_enabled),
                    self._dump_chat_ids(config.recipient_chat_ids),
                ),
            )
        self.conn.commit()

    def enabled_keyword_config(self, keyword: str) -> KeywordConfig | None:
        row = self.conn.execute(
            """
            SELECT keyword, enabled, stats_enabled, task_enabled, alert_enabled, recipient_chat_ids
            FROM keyword_configs WHERE keyword = ?
            """,
            (keyword,),
        ).fetchone()
        if row is None or not bool(row["enabled"]) or not bool(row["alert_enabled"]):
            return None
        chat_ids = self._parse_chat_ids(row["recipient_chat_ids"])
        if not chat_ids:
            return None
        return KeywordConfig(
            keyword=row["keyword"],
            enabled=True,
            recipient_chat_ids=chat_ids,
            alert_enabled=True,
            stats_enabled=bool(row["stats_enabled"]),
            task_enabled=bool(row["task_enabled"]),
        )

    def upsert_message_snapshot(
        self,
        chat_id: str,
        message_id: int,
        sender_user_id: int,
        sender_username: str,
        is_staff: bool,
        text: str,
        message_time: datetime,
        reply_to_message_id: int | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO message_snapshots(
                chat_id, message_id, sender_user_id, sender_username, is_staff,
                text, message_time, reply_to_message_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, message_id) DO UPDATE SET
                sender_user_id = excluded.sender_user_id,
                sender_username = excluded.sender_username,
                is_staff = excluded.is_staff,
                text = excluded.text,
                message_time = excluded.message_time,
                reply_to_message_id = excluded.reply_to_message_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                chat_id,
                message_id,
                sender_user_id,
                sender_username,
                int(is_staff),
                text[:500],
                message_time.isoformat(),
                reply_to_message_id,
            ),
        )
        self.conn.commit()

    def get_message_snapshot(self, chat_id: str, message_id: int) -> MessageSnapshot | None:
        row = self.conn.execute(
            "SELECT * FROM message_snapshots WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id),
        ).fetchone()
        if row is None:
            return None
        return MessageSnapshot(
            chat_id=row["chat_id"],
            message_id=row["message_id"],
            sender_user_id=row["sender_user_id"],
            sender_username=row["sender_username"],
            is_staff=bool(row["is_staff"]),
            text=row["text"],
            message_time=datetime.fromisoformat(row["message_time"]),
            reply_to_message_id=row["reply_to_message_id"],
        )

    def enabled_chat_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS count FROM monitor_rules WHERE enabled = 1").fetchone()
        return int(row["count"])

    def list_enabled_chat_summaries(self) -> list[dict[str, object]]:
        rows = self.conn.execute(
            "SELECT chat_id, chat_name FROM monitor_rules WHERE enabled = 1 ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]

    def create_monitor_task(
        self,
        task_type: str,
        rule_id: int,
        chat_id: str,
        chat_name: str,
        keyword: str,
        staff_user_id: int,
        staff_username: str,
        root_message_id: int,
        wait_message_id: int,
        trigger_message_id: int,
        message_excerpt: str,
        message_url: str,
        recipient_chat_ids: list[int],
        started_at: datetime,
        due_at: datetime,
        status: str = "pending",
    ) -> MonitorTask:
        cur = self.conn.execute(
            """
            INSERT INTO monitor_tasks(
                task_type, status, rule_id, chat_id, chat_name, keyword, staff_user_id,
                staff_username, root_message_id, wait_message_id, trigger_message_id,
                message_excerpt, message_url, recipient_chat_ids, started_at, due_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_type,
                status,
                rule_id,
                chat_id,
                chat_name,
                keyword,
                staff_user_id,
                staff_username,
                root_message_id,
                wait_message_id,
                trigger_message_id,
                message_excerpt,
                message_url,
                self._dump_chat_ids(recipient_chat_ids),
                started_at.isoformat(),
                due_at.isoformat(),
            ),
        )
        self.conn.commit()
        task_id = int(cur.lastrowid)
        for message_id in {root_message_id, wait_message_id, trigger_message_id}:
            self.add_task_context_message(task_id, message_id, commit=False)
        self.conn.commit()
        return self.get_monitor_task(task_id)

    def add_task_context_message(self, task_id: int, message_id: int, commit: bool = True) -> None:
        task = self.get_monitor_task(task_id)
        self.conn.execute(
            """
            INSERT OR IGNORE INTO monitor_task_context_messages(task_id, chat_id, message_id)
            VALUES (?, ?, ?)
            """,
            (task_id, task.chat_id, message_id),
        )
        if commit:
            self.conn.commit()

    def task_context_message_ids(self, task_id: int) -> list[int]:
        rows = self.conn.execute(
            """
            SELECT message_id FROM monitor_task_context_messages
            WHERE task_id = ? ORDER BY message_id
            """,
            (task_id,),
        ).fetchall()
        return [int(row["message_id"]) for row in rows]

    def delete_open_tasks_referencing(self, chat_id: str, message_id: int) -> list[MonitorTask]:
        rows = self.conn.execute(
            """
            SELECT DISTINCT mt.*
            FROM monitor_tasks mt
            LEFT JOIN monitor_task_context_messages ctx ON ctx.task_id = mt.id
            WHERE mt.chat_id = ?
              AND mt.status IN ('pending', 'alerted')
              AND (
                ? IN (mt.root_message_id, mt.wait_message_id, mt.trigger_message_id)
                OR ctx.message_id = ?
              )
            ORDER BY mt.id
            """,
            (chat_id, message_id, message_id),
        ).fetchall()
        if rows:
            self.conn.executemany(
                "UPDATE monitor_tasks SET status = 'deleted' WHERE id = ?",
                [(row["id"],) for row in rows],
            )
            self.conn.commit()
        return [self._task_from_row(row) for row in rows]

    def pending_task_for_context(self, chat_id: str, reply_to_message_id: int) -> MonitorTask | None:
        row = self.conn.execute(
            """
            SELECT mt.*
            FROM monitor_tasks mt
            LEFT JOIN monitor_task_context_messages ctx ON ctx.task_id = mt.id
            WHERE mt.chat_id = ?
              AND mt.status = 'pending'
              AND (
                ? IN (mt.root_message_id, mt.wait_message_id, mt.trigger_message_id)
                OR ctx.message_id = ?
              )
            ORDER BY mt.id DESC
            LIMIT 1
            """,
            (chat_id, reply_to_message_id, reply_to_message_id),
        ).fetchone()
        return self._task_from_row(row) if row else None

    def active_wait_for_reference(self, chat_id: str, root_message_id: int) -> MonitorTask | None:
        row = self.conn.execute(
            """
            SELECT * FROM monitor_tasks
            WHERE chat_id = ?
              AND task_type = 'wait'
              AND status = 'pending'
              AND root_message_id = ?
            ORDER BY id
            LIMIT 1
            """,
            (chat_id, root_message_id),
        ).fetchone()
        return self._task_from_row(row) if row else None

    def earliest_duplicate_wait_for_reference(self, chat_id: str, root_message_id: int) -> MonitorTask | None:
        row = self.conn.execute(
            """
            SELECT * FROM monitor_tasks
            WHERE chat_id = ?
              AND task_type = 'wait'
              AND status = 'duplicate'
              AND root_message_id = ?
            ORDER BY started_at, id
            LIMIT 1
            """,
            (chat_id, root_message_id),
        ).fetchone()
        return self._task_from_row(row) if row else None

    def activate_duplicate_task(self, task_id: int) -> MonitorTask:
        self.conn.execute(
            "UPDATE monitor_tasks SET status = 'pending' WHERE id = ? AND status = 'duplicate'",
            (task_id,),
        )
        self.conn.commit()
        return self.get_monitor_task(task_id)

    def mark_task_deleted(self, task_id: int) -> MonitorTask:
        self.conn.execute(
            "UPDATE monitor_tasks SET status = 'deleted' WHERE id = ?",
            (task_id,),
        )
        self.conn.commit()
        return self.get_monitor_task(task_id)

    def cancel_tasks_referencing(
        self,
        chat_id: str,
        message_id: int,
        status: str = "deleted",
    ) -> list[MonitorTask]:
        rows = self.conn.execute(
            """
            SELECT DISTINCT mt.*
            FROM monitor_tasks mt
            LEFT JOIN monitor_task_context_messages ctx ON ctx.task_id = mt.id
            WHERE mt.chat_id = ?
              AND mt.status = 'pending'
              AND (
                ? IN (mt.root_message_id, mt.wait_message_id, mt.trigger_message_id)
                OR ctx.message_id = ?
              )
            ORDER BY mt.id
            """,
            (chat_id, message_id, message_id),
        ).fetchall()
        if rows:
            self.conn.executemany(
                "UPDATE monitor_tasks SET status = ? WHERE id = ?",
                [(status, row["id"]) for row in rows],
            )
            self.conn.commit()
        return [self._task_from_row(row) for row in rows]

    def latest_pending_task_for_customer(self, chat_id: str, sender_user_id: int) -> MonitorTask | None:
        row = self.conn.execute(
            """
            SELECT * FROM monitor_tasks
            WHERE chat_id = ?
              AND status = 'pending'
              AND task_type IN ('reply', 'followup')
              AND staff_user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (chat_id, sender_user_id),
        ).fetchone()
        return self._task_from_row(row) if row else None

    def get_monitor_task(self, task_id: int) -> MonitorTask:
        row = self.conn.execute("SELECT * FROM monitor_tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._task_from_row(row)

    def _task_from_row(self, row) -> MonitorTask:
        return MonitorTask(
            id=row["id"],
            task_type=row["task_type"],
            status=row["status"],
            rule_id=row["rule_id"],
            chat_id=row["chat_id"],
            chat_name=row["chat_name"],
            keyword=row["keyword"],
            staff_user_id=row["staff_user_id"],
            staff_username=row["staff_username"],
            root_message_id=row["root_message_id"],
            wait_message_id=row["wait_message_id"],
            trigger_message_id=row["trigger_message_id"],
            message_excerpt=row["message_excerpt"],
            message_url=row["message_url"],
            recipient_chat_ids=self._parse_chat_ids(row["recipient_chat_ids"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            due_at=datetime.fromisoformat(row["due_at"]),
            first_alert_sent_at=(
                datetime.fromisoformat(row["first_alert_sent_at"])
                if row["first_alert_sent_at"]
                else None
            ),
            severe_due_at=(datetime.fromisoformat(row["severe_due_at"]) if row["severe_due_at"] else None),
            severe_alert_sent_at=(
                datetime.fromisoformat(row["severe_alert_sent_at"])
                if row["severe_alert_sent_at"]
                else None
            ),
        )

    def complete_tasks_referencing(
        self,
        chat_id: str,
        reply_to_message_id: int,
        completed_at: datetime,
    ) -> list[MonitorTask]:
        rows = self.conn.execute(
            """
            SELECT DISTINCT mt.*
            FROM monitor_tasks mt
            LEFT JOIN monitor_task_context_messages ctx ON ctx.task_id = mt.id
            WHERE mt.chat_id = ?
              AND mt.status IN ('pending', 'alerted')
              AND (
                ? IN (mt.root_message_id, mt.wait_message_id, mt.trigger_message_id)
                OR ctx.message_id = ?
              )
            ORDER BY mt.id
            """,
            (chat_id, reply_to_message_id, reply_to_message_id),
        ).fetchall()
        task_ids = [row["id"] for row in rows]
        if task_ids:
            self.conn.executemany(
                "UPDATE monitor_tasks SET status = 'completed', completed_at = ? WHERE id = ?",
                [(completed_at.isoformat(), task_id) for task_id in task_ids],
            )
            self.conn.commit()
        return [self._task_from_row(row) for row in rows]

    def latest_completed_wait_for_reference(self, chat_id: str, message_id: int) -> MonitorTask | None:
        row = self.conn.execute(
            """
            SELECT DISTINCT mt.*
            FROM monitor_tasks mt
            LEFT JOIN monitor_task_context_messages ctx ON ctx.task_id = mt.id
            WHERE mt.chat_id = ?
              AND mt.task_type = 'wait'
              AND mt.status = 'completed'
              AND (
                ? IN (mt.root_message_id, mt.wait_message_id, mt.trigger_message_id)
                OR ctx.message_id = ?
              )
            ORDER BY mt.id DESC
            LIMIT 1
            """,
            (chat_id, message_id, message_id),
        ).fetchone()
        return self._task_from_row(row) if row else None

    def recipient_display_for_user(self, telegram_user_id: int, fallback_username: str = "") -> dict[str, str]:
        staff = self.conn.execute(
            """
            SELECT display_name, telegram_username
            FROM rule_staff
            WHERE telegram_user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (telegram_user_id,),
        ).fetchone()
        hit = self.conn.execute(
            """
            SELECT telegram_username
            FROM keyword_hits
            WHERE telegram_user_id = ?
              AND telegram_username != ''
            ORDER BY message_time DESC, id DESC
            LIMIT 1
            """,
            (telegram_user_id,),
        ).fetchone()
        username = fallback_username or (hit["telegram_username"] if hit else "")
        if staff is not None:
            staff_name = staff["display_name"]
            staff_username = staff["telegram_username"] or username
            if not self._is_placeholder_display_name(staff_name, telegram_user_id):
                return {"display_name": staff_name, "telegram_username": staff_username}
            if staff_username:
                return {"display_name": staff_username, "telegram_username": staff_username}
        return {"display_name": username or str(telegram_user_id), "telegram_username": username}

    @staticmethod
    def _is_placeholder_display_name(display_name: str, telegram_user_id: int) -> bool:
        normalized = display_name.strip().lower()
        return normalized in {"", "test-staff", "test staff", str(telegram_user_id)}

    def mark_task_alerted(self, task_id: int, alerted_at: datetime) -> None:
        self.conn.execute(
            "UPDATE monitor_tasks SET status = 'alerted', alert_sent_at = ? WHERE id = ?",
            (alerted_at.isoformat(), task_id),
        )
        self.conn.commit()

    def mark_first_alert_sent(
        self,
        task_id: int,
        alerted_at: datetime,
        severe_due_at: datetime,
    ) -> None:
        self.conn.execute(
            """
            UPDATE monitor_tasks
            SET status = 'alerted',
                alert_sent_at = ?,
                first_alert_sent_at = COALESCE(first_alert_sent_at, ?),
                severe_due_at = COALESCE(severe_due_at, ?)
            WHERE id = ? AND status IN ('pending', 'alerted')
            """,
            (alerted_at.isoformat(), alerted_at.isoformat(), severe_due_at.isoformat(), task_id),
        )
        self.conn.commit()

    def list_due_severe_tasks(self, now: datetime) -> list[MonitorTask]:
        rows = self.conn.execute(
            """
            SELECT * FROM monitor_tasks
            WHERE status = 'alerted'
              AND first_alert_sent_at IS NOT NULL
              AND severe_due_at IS NOT NULL
              AND severe_alert_sent_at IS NULL
              AND datetime(severe_due_at) <= datetime(?)
            ORDER BY severe_due_at, id
            """,
            (now.isoformat(),),
        ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def mark_severe_alert_sent(self, task_id: int, sent_at: datetime) -> None:
        self.conn.execute(
            """
            UPDATE monitor_tasks
            SET severe_alert_sent_at = COALESCE(severe_alert_sent_at, ?)
            WHERE id = ? AND status = 'alerted'
            """,
            (sent_at.isoformat(), task_id),
        )
        self.conn.commit()

    def mark_stale_overdue_tasks_alerted(self, now: datetime, grace_minutes: int = 2) -> None:
        cutoff = now - timedelta(minutes=grace_minutes)
        self.conn.execute(
            """
            UPDATE monitor_tasks
            SET status = 'alerted', alert_sent_at = ?
            WHERE status = 'pending'
              AND datetime(due_at) < datetime(?)
            """,
            (now.isoformat(), cutoff.isoformat()),
        )
        self.conn.commit()

    def task_recipient_chat_ids(self, task_id: int) -> list[int]:
        row = self.conn.execute(
            "SELECT recipient_chat_ids FROM monitor_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return []
        return self._parse_chat_ids(row["recipient_chat_ids"])

    def list_open_tasks(self) -> list[MonitorTask]:
        rows = self.conn.execute(
            """
            SELECT * FROM monitor_tasks
            WHERE status = 'pending'
               OR (status = 'alerted' AND first_alert_sent_at IS NOT NULL)
            ORDER BY due_at, id
            """
        ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def history_check_summary(self, limit: int = 20, now: datetime | None = None) -> dict[str, object]:
        now = now or datetime.now().astimezone()
        local_now = now.astimezone(DISPLAY_TZ) if now.tzinfo else now.replace(tzinfo=DISPLAY_TZ)
        today = local_now.date().isoformat()
        rows = self.conn.execute(
            """
            SELECT task_type, status, COUNT(*) AS count
            FROM monitor_tasks
            WHERE date(datetime(started_at), '+8 hours') = ?
              AND status != 'deleted'
            GROUP BY task_type, status
            ORDER BY task_type, status
            """,
            (today,),
        ).fetchall()
        wait_rows = self.conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM monitor_tasks
            WHERE task_type = 'wait'
              AND date(datetime(started_at), '+8 hours') = ?
              AND status != 'deleted'
            GROUP BY status
            """
            ,
            (today,),
        ).fetchall()
        wait_counts = {row["status"]: int(row["count"]) for row in wait_rows}
        wait_total = sum(wait_counts.values())
        completed_count = wait_counts.get("completed", 0)
        anomaly_rows = self.conn.execute(
            """
            SELECT
                CASE
                    WHEN status = 'alerted' THEN 'alerted'
                    WHEN status = 'duplicate' THEN 'duplicate'
                    WHEN task_type IN ('followup', 'reply', 'self_reply') THEN task_type
                    ELSE 'other'
                END AS key,
                COUNT(*) AS count
            FROM monitor_tasks
            WHERE date(datetime(started_at), '+8 hours') = ?
              AND status != 'deleted'
              AND (
                status IN ('alerted', 'duplicate')
                OR task_type IN ('followup', 'reply', 'self_reply')
              )
            GROUP BY key
            ORDER BY key
            """,
            (today,),
        ).fetchall()
        anomaly_items = self.conn.execute(
            """
            SELECT
                id,
                CASE
                    WHEN status = 'alerted' THEN 'alerted'
                    WHEN status = 'duplicate' THEN 'duplicate'
                    WHEN task_type IN ('followup', 'reply', 'self_reply') THEN task_type
                    ELSE 'other'
                END AS key,
                task_type,
                status,
                chat_name,
                keyword,
                message_excerpt,
                message_url,
                started_at,
                created_at
            FROM monitor_tasks
            WHERE date(datetime(started_at), '+8 hours') = ?
              AND status != 'deleted'
              AND (
                status IN ('alerted', 'duplicate')
                OR task_type IN ('followup', 'reply', 'self_reply')
              )
            ORDER BY datetime(started_at) DESC, id DESC
            LIMIT ?
            """,
            (today, limit),
        ).fetchall()
        closed_loop = {
            "total": wait_total,
            "completed": completed_count,
            "pending": wait_counts.get("pending", 0),
            "alerted": wait_counts.get("alerted", 0),
            "deleted": 0,
            "duplicate": wait_counts.get("duplicate", 0),
            "completion_rate": int(round((completed_count / wait_total) * 100)) if wait_total else 0,
        }
        anomaly_item_dicts = [
            {**dict(row), "label": ANOMALY_LABELS.get(row["key"], row["key"])}
            for row in anomaly_items
        ]
        return {
            "date": today,
            "scope_label": f"{today} 北京时间",
            "closed_loop": closed_loop,
            "anomaly_counts": [
                {**dict(row), "label": ANOMALY_LABELS.get(row["key"], row["key"])}
                for row in anomaly_rows
            ],
            "anomaly_items": anomaly_item_dicts,
            "counts": [dict(row) for row in rows],
            "open_items": anomaly_item_dicts,
        }

    def list_due_pending_tasks(self, now: datetime) -> list[MonitorTask]:
        rows = self.conn.execute(
            """
            SELECT * FROM monitor_tasks
            WHERE status = 'pending'
              AND datetime(due_at) <= datetime(?)
            ORDER BY due_at, id
            """,
            (now.isoformat(),),
        ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def record_alert_delivery(
        self,
        rule_id: int,
        chat_id: str,
        message_id: int,
        matched_keyword: str,
        staff_telegram_user_id: int,
        staff_telegram_username: str,
        staff_display_name: str,
        status: str,
        error_message: str,
        sent_at: datetime | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO alert_deliveries(
                rule_id, chat_id, message_id, matched_keyword,
                staff_telegram_user_id, staff_telegram_username, staff_display_name,
                status, error_message, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                chat_id,
                message_id,
                matched_keyword,
                staff_telegram_user_id,
                staff_telegram_username,
                staff_display_name,
                status,
                error_message,
                sent_at.isoformat() if sent_at else None,
            ),
        )
        self.conn.commit()
