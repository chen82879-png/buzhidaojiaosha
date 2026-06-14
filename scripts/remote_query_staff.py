import os
import sys
import time

import paramiko


HOST = "159.223.138.63"
USER = "root"


REMOTE_PY = """
import json
import sqlite3

conn = sqlite3.connect('/var/lib/telegram-alert-bot/telegram_alert_bot.sqlite3')
conn.row_factory = sqlite3.Row

queries = {
    "test_staff_rows": (
        "SELECT id, rule_id, telegram_user_id, telegram_username, display_name, enabled "
        "FROM rule_staff WHERE display_name LIKE '%test%' ORDER BY id"
    ),
    "elk_staff_rows": (
        "SELECT id, rule_id, telegram_user_id, telegram_username, display_name, enabled "
        "FROM rule_staff WHERE telegram_user_id = 7511822833 ORDER BY id"
    ),
    "elk_recent_hits": (
        "SELECT telegram_user_id, telegram_username, matched_keyword, message_time "
        "FROM keyword_hits WHERE telegram_user_id = 7511822833 AND telegram_username != '' "
        "ORDER BY id DESC LIMIT 8"
    ),
}

payload = {}
for name, sql in queries.items():
    payload[name] = [dict(row) for row in conn.execute(sql).fetchall()]
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
        remote_script = f"/tmp/remote_query_staff_{int(time.time())}.py"
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
