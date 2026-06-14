import os
import sys

import paramiko


HOST = "159.223.138.63"
USER = "root"


COMMAND = r"""
cd /opt/telegram-alert-bot &&
set -a && . ./.env && set +a &&
.venv/bin/python - <<'PY'
from app.db import connect
from app.matcher import match_message
from app.repositories import Repository
import os

conn = connect(os.environ["SQLITE_PATH"])
repo = Repository(conn)
rules = repo.list_enabled_rules()
print("enabled_rules", len(rules))
for chat_id, text in [
    ("-1001571955528", "请稍等ART"),
    ("-1001885279888", "请稍等-MAD"),
    ("-1002807120955", "稍等-XW"),
]:
    result = match_message(chat_id, text, rules)
    print(chat_id, text, result.matched_keywords if result else None)
PY
systemctl is-active telegram-alert-bot
systemctl is-active telegram-alert-listener
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
        _stdin, stdout, stderr = client.exec_command(COMMAND, timeout=120)
        code = stdout.channel.recv_exit_status()
        print(stdout.read().decode("utf-8", "replace"))
        err = stderr.read().decode("utf-8", "replace")
        if err:
            print(err, file=sys.stderr)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
