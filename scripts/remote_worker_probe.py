import os
import sys
import time

import paramiko


HOST = "159.223.138.63"
USER = "root"


REMOTE_PY = """
import datetime
import os
import subprocess
import time

def sh(command):
    return subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT).strip()

pid = sh("systemctl show -p MainPID --value telegram-alert-bot")
print("bot_pid", pid)
env_path = f"/proc/{pid}/environ"
env = {}
if os.path.exists(env_path):
    raw = open(env_path, "rb").read()
    for item in raw.split(b"\\0"):
        if b"=" in item:
            key, value = item.split(b"=", 1)
            env[key.decode()] = value.decode(errors="replace")
print("env_has", {
    "TELEGRAM_BOT_TOKEN": bool(env.get("TELEGRAM_BOT_TOKEN")),
    "REDIS_URL": bool(env.get("REDIS_URL")),
    "SQLITE_PATH": bool(env.get("SQLITE_PATH")),
})
print("now", time.time(), datetime.datetime.utcfromtimestamp(time.time()).isoformat())
print("queue_size", sh("redis-cli ZCARD timeout_queue"))
print("due_count", sh(f"redis-cli ZCOUNT timeout_queue 0 {int(time.time())}"))
print("oldest_due", sh("redis-cli ZRANGE timeout_queue 0 2 WITHSCORES"))

import sqlite3
conn = sqlite3.connect("/var/lib/telegram-alert-bot/telegram_alert_bot.sqlite3")
conn.row_factory = sqlite3.Row
ids = [353, 354, 364, 376, 395, 397, 400]
rows = conn.execute(
    f"SELECT id, task_type, status, keyword, due_at, alert_sent_at FROM monitor_tasks WHERE id IN ({','.join('?' for _ in ids)}) ORDER BY id",
    ids,
).fetchall()
print("queued_task_db_status", [dict(row) for row in rows])
print("service_status")
print(sh("systemctl status telegram-alert-bot --no-pager -n 80"))
print("process")
print(sh("ps -o pid,lstart,cmd -p $(systemctl show -p MainPID --value telegram-alert-bot)"))
print("code_probe")
print(sh("cd /opt/telegram-alert-bot && grep -n -E 'timeout_worker_loop|startup|mark_task_alerted|send_timeout_alert' app/main.py app/worker.py"))
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
        remote_script = f"/tmp/remote_worker_probe_{int(time.time())}.py"
        with client.open_sftp() as sftp:
            with sftp.file(remote_script, "w") as remote_file:
                remote_file.write(REMOTE_PY)
        command = f"python3 {remote_script}; rm -f {remote_script}"
        print(f"$ {command}")
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
