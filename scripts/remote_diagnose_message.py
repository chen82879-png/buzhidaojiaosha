import os
import sys
import time

import paramiko


HOST = "159.223.138.63"
USER = "root"
CHAT_ID = "-1001931146238"
MESSAGE_ID = "825084"
KEYWORD = "请稍等elk"
DB_PATH = "/var/lib/telegram-alert-bot/telegram_alert_bot.sqlite3"


REMOTE_PY = f"""
import json
import sqlite3
from pathlib import Path

db_path = Path({DB_PATH!r})
print("db_exists", db_path.exists(), db_path)
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

def rows(sql, params=()):
    return [dict(row) for row in conn.execute(sql, params).fetchall()]

payload = {{
    "group_rule": rows(
        "SELECT id, chat_id, chat_name, enabled FROM monitor_rules WHERE chat_id = ?",
        ({CHAT_ID!r},),
    ),
    "keyword_config": rows(
        "SELECT keyword, enabled, recipient_chat_ids FROM keyword_configs WHERE keyword = ?",
        ({KEYWORD!r},),
    ),
    "keyword_hits_exact_message": rows(
        "SELECT id, chat_id, chat_name, message_id, telegram_user_id, telegram_username, matched_keyword, message_excerpt, message_time FROM keyword_hits WHERE chat_id = ? AND message_id = ?",
        ({CHAT_ID!r}, int({MESSAGE_ID!r})),
    ),
    "keyword_hits_recent_elk": rows(
        "SELECT id, chat_id, chat_name, message_id, telegram_user_id, telegram_username, matched_keyword, message_excerpt, message_time FROM keyword_hits WHERE matched_keyword = ? ORDER BY id DESC LIMIT 10",
        ({KEYWORD!r},),
    ),
    "tasks_exact_message": rows(
        "SELECT id, task_type, status, chat_id, chat_name, keyword, staff_user_id, staff_username, root_message_id, wait_message_id, trigger_message_id, started_at, due_at, alert_sent_at FROM monitor_tasks WHERE chat_id = ? AND ? IN (root_message_id, wait_message_id, trigger_message_id)",
        ({CHAT_ID!r}, int({MESSAGE_ID!r})),
    ),
    "tasks_recent_elk": rows(
        "SELECT id, task_type, status, chat_id, chat_name, keyword, staff_user_id, staff_username, root_message_id, wait_message_id, trigger_message_id, started_at, due_at, alert_sent_at FROM monitor_tasks WHERE keyword = ? ORDER BY id DESC LIMIT 10",
        ({KEYWORD!r},),
    ),
}}
print(json.dumps(payload, ensure_ascii=False, indent=2))
"""


COMMANDS = [
    "systemctl is-active telegram-alert-bot || true",
    "systemctl is-active telegram-alert-listener || true",
    "journalctl -u telegram-alert-listener --since '2026-06-09 00:00:00' --no-pager -n 120 || true",
    "journalctl -u telegram-alert-bot --since '2026-06-09 00:00:00' --no-pager -n 80 || true",
    "systemctl status redis-server --no-pager -n 20 2>/dev/null || systemctl status redis --no-pager -n 20 2>/dev/null || true",
    "redis-cli INFO server | grep -E 'uptime_in_seconds|process_id|redis_version' || true",
    "redis-cli INFO persistence | grep -E 'rdb_last_save_time|rdb_changes_since_last_save|aof_enabled|aof_last_write_status' || true",
    "redis-cli --scan --pattern 'telegram-alert-bot*' | head -80 || true",
]


def main() -> int:
    password = os.getenv("SSH_PASSWORD")
    if not password:
        print("SSH_PASSWORD is required", file=sys.stderr)
        return 2
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=20)
    try:
        remote_script = f"/tmp/remote_diagnose_message_{int(time.time())}.py"
        with client.open_sftp() as sftp:
            with sftp.file(remote_script, "w") as remote_file:
                remote_file.write(REMOTE_PY)
        COMMANDS.insert(4, f"cd /opt/telegram-alert-bot && ./.venv/bin/python {remote_script}; rm -f {remote_script}")
        for command in COMMANDS:
            print(f"\n$ {command}")
            _stdin, stdout, stderr = client.exec_command(command, timeout=60)
            code = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8", "replace").strip()
            err = stderr.read().decode("utf-8", "replace").strip()
            print(f"exit={code}")
            if out:
                print(out)
            if err:
                print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
