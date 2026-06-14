import os
import sys
import time

import paramiko


HOST = "159.223.138.63"
USER = "root"


REMOTE_PY = """
import os

for line in open('/opt/telegram-alert-bot/.env', encoding='utf-8'):
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    os.environ.setdefault(key, value)

from app.config import load_settings
from app.db import connect, migrate
from app.repositories import Repository

settings = load_settings()
conn = connect(settings.sqlite_path)
migrate(conn)
repo = Repository(conn)
print(repo.recipient_display_for_user(7511822833))
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
        remote_script = f"/tmp/remote_verify_recipient_display_{int(time.time())}.py"
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
