import os
import sys
import time

import paramiko


HOST = "159.223.138.63"
USER = "root"


REMOTE_PY = """
import json
import sqlite3

DB = "/var/lib/telegram-alert-bot/telegram_alert_bot.sqlite3"
KEYWORD = "请稍等elk"

# 2026-06-10 Asia/Shanghai == 2026-06-09 16:00:00 UTC through 2026-06-10 15:59:59 UTC.
START = "2026-06-09T16:00:00+00:00"
END = "2026-06-10T16:00:00+00:00"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

def rows(sql, params=()):
    return [dict(row) for row in conn.execute(sql, params).fetchall()]

payload = {
    "keyword_config": rows(
        "SELECT keyword, enabled, recipient_chat_ids, updated_at FROM keyword_configs WHERE keyword = ?",
        (KEYWORD,),
    ),
    "hits_summary": rows(
        '''
        SELECT chat_id, chat_name, telegram_user_id, telegram_username, COUNT(*) AS count,
               MIN(message_time) AS first_time, MAX(message_time) AS last_time
        FROM keyword_hits
        WHERE matched_keyword = ?
          AND datetime(message_time) >= datetime(?)
          AND datetime(message_time) < datetime(?)
        GROUP BY chat_id, chat_name, telegram_user_id, telegram_username
        ORDER BY count DESC, last_time DESC
        ''',
        (KEYWORD, START, END),
    ),
    "tasks_summary": rows(
        '''
        SELECT status, task_type, COUNT(*) AS count,
               MIN(started_at) AS first_started, MAX(started_at) AS last_started
        FROM monitor_tasks
        WHERE keyword = ?
          AND datetime(started_at) >= datetime(?)
          AND datetime(started_at) < datetime(?)
        GROUP BY status, task_type
        ORDER BY task_type, status
        ''',
        (KEYWORD, START, END),
    ),
    "suspicious_completed_after_due": rows(
        '''
        SELECT id, task_type, status, chat_id, chat_name, staff_user_id, staff_username,
               root_message_id, wait_message_id, trigger_message_id,
               started_at, due_at, completed_at, alert_sent_at, message_url,
               CAST((julianday(completed_at) - julianday(due_at)) * 24 * 60 AS INTEGER) AS minutes_after_due
        FROM monitor_tasks
        WHERE keyword = ?
          AND status = 'completed'
          AND alert_sent_at IS NULL
          AND completed_at IS NOT NULL
          AND datetime(completed_at) > datetime(due_at)
          AND datetime(started_at) >= datetime(?)
          AND datetime(started_at) < datetime(?)
        ORDER BY due_at
        LIMIT 80
        ''',
        (KEYWORD, START, END),
    ),
    "alerted_tasks": rows(
        '''
        SELECT id, task_type, status, chat_id, chat_name, staff_user_id, staff_username,
               root_message_id, wait_message_id, trigger_message_id,
               started_at, due_at, completed_at, alert_sent_at, message_url
        FROM monitor_tasks
        WHERE keyword = ?
          AND alert_sent_at IS NOT NULL
          AND datetime(started_at) >= datetime(?)
          AND datetime(started_at) < datetime(?)
        ORDER BY alert_sent_at DESC
        LIMIT 40
        ''',
        (KEYWORD, START, END),
    ),
    "pending_overdue_now": rows(
        '''
        SELECT id, task_type, status, chat_id, chat_name, staff_user_id, staff_username,
               root_message_id, wait_message_id, trigger_message_id,
               started_at, due_at, completed_at, alert_sent_at, message_url
        FROM monitor_tasks
        WHERE keyword = ?
          AND status = 'pending'
          AND datetime(due_at) < datetime('now')
        ORDER BY due_at
        LIMIT 40
        ''',
        (KEYWORD,),
    ),
    "deliveries_recent": rows(
        '''
        SELECT id, rule_id, chat_id, message_id, matched_keyword, staff_telegram_user_id,
               staff_telegram_username, staff_display_name, status, error_message, sent_at, created_at
        FROM alert_deliveries
        WHERE matched_keyword = ?
          AND datetime(created_at) >= datetime(?)
        ORDER BY id DESC
        LIMIT 40
        ''',
        (KEYWORD, START),
    ),
}

print(json.dumps(payload, ensure_ascii=False, indent=2))
"""


REMOTE_QUEUE_PY = """
import json
import os
import subprocess

def sh(command):
    return subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT).strip()

payload = {
    "bot_active": sh("systemctl is-active telegram-alert-bot || true"),
    "listener_active": sh("systemctl is-active telegram-alert-listener || true"),
    "queue_size": sh("redis-cli ZCARD timeout_queue || true"),
    "due_count": sh("redis-cli ZCOUNT timeout_queue 0 $(date +%s) || true"),
    "queue_head": sh("redis-cli ZRANGE timeout_queue 0 20 WITHSCORES || true"),
    "bot_logs": sh("journalctl -u telegram-alert-bot --since '2026-06-10 00:00:00' --no-pager -n 120 || true"),
    "listener_logs": sh("journalctl -u telegram-alert-listener --since '2026-06-10 00:00:00' --no-pager -n 80 || true"),
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
"""


def main() -> int:
    password = os.getenv("SSH_PASSWORD")
    if not password:
        print("SSH_PASSWORD is required", file=sys.stderr)
        return 2
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=20)
    try:
        scripts = [
            (f"/tmp/remote_audit_elk_yesterday_{int(time.time())}.py", REMOTE_PY),
            (f"/tmp/remote_audit_elk_queue_{int(time.time())}.py", REMOTE_QUEUE_PY),
        ]
        with client.open_sftp() as sftp:
            for path, body in scripts:
                with sftp.file(path, "w") as remote_file:
                    remote_file.write(body)
        for path, _body in scripts:
            command = f"cd /opt/telegram-alert-bot && ./.venv/bin/python {path}; rm -f {path}"
            print(f"\\n$ {command}")
            _stdin, stdout, stderr = client.exec_command(command, timeout=90)
            print(stdout.read().decode("utf-8", "replace").strip())
            err = stderr.read().decode("utf-8", "replace").strip()
            if err:
                print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
