from __future__ import annotations

import os
import sqlite3


def count_rows(conn: sqlite3.Connection, table: str) -> int | str:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error as exc:
        return f"unavailable ({exc})"


def main() -> None:
    sqlite_path = os.environ.get("SQLITE_PATH", "./data/telegram_alert_bot.sqlite3")
    print(f"SQLITE_PATH={sqlite_path}")
    if not os.path.exists(sqlite_path):
        print("database=missing")
        return
    conn = sqlite3.connect(sqlite_path)
    try:
        for table in [
            "monitor_rules",
            "rule_keywords",
            "rule_staff",
            "keyword_configs",
            "keyword_hits",
            "keyword_daily_stats",
            "alert_deliveries",
            "monitor_tasks",
            "monitor_task_context_messages",
        ]:
            print(f"{table}={count_rows(conn, table)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
