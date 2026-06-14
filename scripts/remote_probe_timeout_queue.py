import os
import sys
import time

import paramiko


HOST = "159.223.138.63"
USER = "root"


REMOTE_PY = """
import json
import sqlite3
import subprocess

def sh(command):
    return subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT).strip()

raw = sh("redis-cli ZRANGE timeout_queue 0 -1")
task_ids = [int(item) for item in raw.splitlines() if item.strip().isdigit()]
conn = sqlite3.connect('/var/lib/telegram-alert-bot/telegram_alert_bot.sqlite3')
conn.row_factory = sqlite3.Row
rows = []
if task_ids:
    placeholders = ",".join("?" for _ in task_ids)
    rows = [
        dict(row)
        for row in conn.execute(
            f'''
            SELECT id, keyword, task_type, status, chat_id, chat_name, staff_user_id, staff_username,
                   root_message_id, wait_message_id, trigger_message_id, started_at, due_at,
                   completed_at, alert_sent_at, message_url
            FROM monitor_tasks
            WHERE id IN ({placeholders})
            ORDER BY id
            ''',
            task_ids,
        ).fetchall()
    ]
payload = {
    "task_ids": task_ids,
    "rows": rows,
    "alerted_keys": {str(task_id): bool(sh(f"redis-cli EXISTS alerted-task:{task_id}") == "1") for task_id in task_ids},
    "pending_keys": {str(task_id): bool(sh(f"redis-cli EXISTS pending-task:{task_id}") == "1") for task_id in task_ids},
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
        remote_script = f"/tmp/remote_probe_timeout_queue_{int(time.time())}.py"
        with client.open_sftp() as sftp:
            with sftp.file(remote_script, "w") as remote_file:
                remote_file.write(REMOTE_PY)
        command = f"cd /opt/telegram-alert-bot && ./.venv/bin/python {remote_script}; rm -f {remote_script}"
        _stdin, stdout, stderr = client.exec_command(command, timeout=60)
        print(stdout.read().decode("utf-8", "replace").strip())
        err = stderr.read().decode("utf-8", "replace").strip()
        if err:
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
