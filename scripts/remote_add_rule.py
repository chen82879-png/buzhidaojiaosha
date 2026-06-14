import os
import shlex
import sys

import paramiko


HOST = "159.223.138.63"
USER = "root"


def main() -> int:
    password = os.getenv("SSH_PASSWORD")
    chat_id = os.getenv("MONITOR_CHAT_ID")
    keyword = os.getenv("MONITOR_KEYWORD")
    staff_user_id = os.getenv("STAFF_USER_ID")
    staff_name = os.getenv("STAFF_NAME", "test-staff")
    if not password or not chat_id or not keyword or not staff_user_id:
        print("SSH_PASSWORD, MONITOR_CHAT_ID, MONITOR_KEYWORD, STAFF_USER_ID are required", file=sys.stderr)
        return 2

    command = " ".join(
        [
            "cd /opt/telegram-alert-bot",
            "&& set -a && . ./.env && set +a",
            "&& .venv/bin/python scripts/add_monitor_rule.py",
            "--chat-id",
            shlex.quote(chat_id),
            "--chat-name",
            shlex.quote("test-chat"),
            "--keywords",
            shlex.quote(keyword),
            "--staff-user-id",
            shlex.quote(staff_user_id),
            "--staff-name",
            shlex.quote(staff_name),
        ]
    )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=20)
    try:
        _stdin, stdout, stderr = client.exec_command(command, timeout=60)
        code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        print(out)
        if err:
            print(err, file=sys.stderr)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
