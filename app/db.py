import sqlite3
from pathlib import Path


def connect(sqlite_path: str) -> sqlite3.Connection:
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS monitor_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL UNIQUE,
            chat_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rule_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL REFERENCES monitor_rules(id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rule_id, keyword)
        );
        CREATE TABLE IF NOT EXISTS rule_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL REFERENCES monitor_rules(id) ON DELETE CASCADE,
            telegram_user_id INTEGER NOT NULL,
            telegram_username TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rule_id, telegram_user_id)
        );
        CREATE TABLE IF NOT EXISTS keyword_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL REFERENCES monitor_rules(id) ON DELETE CASCADE,
            chat_id TEXT NOT NULL,
            chat_name TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            telegram_user_id INTEGER NOT NULL,
            telegram_username TEXT NOT NULL DEFAULT '',
            matched_keyword TEXT NOT NULL,
            message_excerpt TEXT NOT NULL,
            message_url TEXT NOT NULL,
            message_time TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS keyword_daily_stats (
            stat_date TEXT NOT NULL,
            matched_keyword TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            chat_name TEXT NOT NULL,
            telegram_user_id INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (stat_date, matched_keyword, chat_id, telegram_user_id)
        );
        CREATE TABLE IF NOT EXISTS alert_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            matched_keyword TEXT NOT NULL,
            staff_telegram_user_id INTEGER NOT NULL,
            staff_telegram_username TEXT NOT NULL,
            staff_display_name TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT NOT NULL DEFAULT '',
            sent_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS keyword_configs (
            keyword TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0,
            stats_enabled INTEGER NOT NULL DEFAULT 1,
            task_enabled INTEGER NOT NULL DEFAULT 1,
            alert_enabled INTEGER NOT NULL DEFAULT 1,
            recipient_chat_ids TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS message_snapshots (
            chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            sender_user_id INTEGER NOT NULL,
            sender_username TEXT NOT NULL DEFAULT '',
            sender_display_name TEXT NOT NULL DEFAULT '',
            is_staff INTEGER NOT NULL DEFAULT 0,
            text TEXT NOT NULL DEFAULT '',
            message_time TEXT NOT NULL,
            reply_to_message_id INTEGER,
            media_group_id INTEGER,
            message_kind TEXT NOT NULL DEFAULT 'text',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, message_id)
        );
        CREATE TABLE IF NOT EXISTS monitor_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            rule_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            chat_name TEXT NOT NULL,
            keyword TEXT NOT NULL,
            staff_user_id INTEGER NOT NULL,
            staff_username TEXT NOT NULL DEFAULT '',
            root_message_id INTEGER NOT NULL,
            wait_message_id INTEGER NOT NULL,
            trigger_message_id INTEGER NOT NULL,
            message_excerpt TEXT NOT NULL,
            message_url TEXT NOT NULL,
            recipient_chat_ids TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            due_at TEXT NOT NULL,
            completed_at TEXT,
            alert_sent_at TEXT,
            first_alert_sent_at TEXT,
            severe_due_at TEXT,
            severe_alert_sent_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS monitor_task_context_messages (
            task_id INTEGER NOT NULL REFERENCES monitor_tasks(id) ON DELETE CASCADE,
            chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (task_id, message_id)
        );
        CREATE INDEX IF NOT EXISTS idx_monitor_tasks_deleted_wait_lookup
            ON monitor_tasks(chat_id, wait_message_id, task_type, status);
        CREATE TABLE IF NOT EXISTS automation_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            result_json TEXT,
            error_message TEXT NOT NULL DEFAULT '',
            request_chat_id TEXT NOT NULL DEFAULT '',
            request_message_id INTEGER,
            claimed_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            claimed_at TEXT,
            finished_at TEXT,
            expires_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_automation_commands_status_created
            ON automation_commands(status, created_at);
        """
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(keyword_configs)").fetchall()}
    if "alert_enabled" not in columns:
        conn.execute("ALTER TABLE keyword_configs ADD COLUMN alert_enabled INTEGER NOT NULL DEFAULT 1")
    if "stats_enabled" not in columns:
        conn.execute("ALTER TABLE keyword_configs ADD COLUMN stats_enabled INTEGER NOT NULL DEFAULT 1")
        conn.execute("UPDATE keyword_configs SET stats_enabled = enabled")
    if "task_enabled" not in columns:
        conn.execute("ALTER TABLE keyword_configs ADD COLUMN task_enabled INTEGER NOT NULL DEFAULT 1")
        conn.execute("UPDATE keyword_configs SET task_enabled = enabled")
    task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(monitor_tasks)").fetchall()}
    if "first_alert_sent_at" not in task_columns:
        conn.execute("ALTER TABLE monitor_tasks ADD COLUMN first_alert_sent_at TEXT")
    if "severe_due_at" not in task_columns:
        conn.execute("ALTER TABLE monitor_tasks ADD COLUMN severe_due_at TEXT")
    if "severe_alert_sent_at" not in task_columns:
        conn.execute("ALTER TABLE monitor_tasks ADD COLUMN severe_alert_sent_at TEXT")
    snapshot_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(message_snapshots)").fetchall()
    }
    if "sender_display_name" not in snapshot_columns:
        conn.execute("ALTER TABLE message_snapshots ADD COLUMN sender_display_name TEXT NOT NULL DEFAULT ''")
    if "media_group_id" not in snapshot_columns:
        conn.execute("ALTER TABLE message_snapshots ADD COLUMN media_group_id INTEGER")
    if "message_kind" not in snapshot_columns:
        conn.execute("ALTER TABLE message_snapshots ADD COLUMN message_kind TEXT NOT NULL DEFAULT 'text'")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_message_snapshots_media_group "
        "ON message_snapshots(chat_id, media_group_id)"
    )
    conn.commit()
