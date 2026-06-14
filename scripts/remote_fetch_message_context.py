import os
import sys
import time

import paramiko


HOST = "159.223.138.63"
USER = "root"
CHAT_ID = -1001931146238
TARGET_IDS = list(range(825080, 825520))


REMOTE_PY = f"""
import asyncio
import json
import os
import shutil
import time
from pathlib import Path

from telethon import TelegramClient

from app.config import load_settings

for line in open("/opt/telegram-alert-bot/.env", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key, value)

settings = load_settings()

async def main():
    session_copy = f"/tmp/telegram-alert-diagnose-session-{{int(time.time())}}"
    source_session = Path(settings.telethon_session_path)
    if not source_session.exists() and source_session.with_suffix(".session").exists():
        source_session = source_session.with_suffix(".session")
    shutil.copyfile(source_session, session_copy + ".session")
    client = TelegramClient(session_copy, settings.telegram_api_id, settings.telegram_api_hash)
    await client.start(phone=settings.listener_phone)
    messages = await client.get_messages({CHAT_ID}, ids={TARGET_IDS!r})
    rows = []
    for msg in messages:
        if msg is None:
            continue
        reply_to = getattr(msg, "reply_to_msg_id", None)
        text = getattr(msg, "raw_text", "") or getattr(msg, "text", "") or ""
        if reply_to not in (825084, 825085) and not ("jrjn1688" in text or "5342580788109848" in text):
            continue
        sender = await msg.get_sender()
        rows.append({{
            "id": msg.id,
            "date": msg.date.isoformat() if msg.date else "",
            "sender_id": msg.sender_id,
            "sender_username": getattr(sender, "username", "") or "",
            "reply_to": reply_to,
            "text": text[:200],
            "has_media": bool(getattr(msg, "media", None)),
        }})
    await client.disconnect()
    try:
        os.remove(session_copy + ".session")
    except OSError:
        pass
    print(json.dumps(rows, ensure_ascii=False, indent=2))

asyncio.run(main())
"""


REMOTE_DB_PY = """
import json
import sqlite3

conn = sqlite3.connect('/var/lib/telegram-alert-bot/telegram_alert_bot.sqlite3')
conn.row_factory = sqlite3.Row
rows = conn.execute(
    '''
    SELECT id, task_type, status, chat_id, keyword, staff_user_id, staff_username,
           root_message_id, wait_message_id, trigger_message_id,
           started_at, due_at, completed_at, alert_sent_at
    FROM monitor_tasks
    WHERE chat_id = '-1001931146238'
      AND 825084 IN (root_message_id, wait_message_id, trigger_message_id)
    '''
).fetchall()
delivery_columns = [row["name"] for row in conn.execute("PRAGMA table_info(alert_deliveries)").fetchall()]
select_columns = ", ".join(delivery_columns)
deliveries = []
if select_columns:
    deliveries = conn.execute(
        f'''
        SELECT {select_columns}
        FROM alert_deliveries
        WHERE chat_id = '-1001931146238'
          AND message_id IN (825084, 825085)
        ORDER BY id DESC
        '''
    ).fetchall()
print(json.dumps({
    "tasks": [dict(row) for row in rows],
    "delivery_columns": delivery_columns,
    "deliveries": [dict(row) for row in deliveries],
}, ensure_ascii=False, indent=2))
"""


COMMANDS = []


def main() -> int:
    password = os.getenv("SSH_PASSWORD")
    if not password:
        print("SSH_PASSWORD is required", file=sys.stderr)
        return 2
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=20)
    try:
        timestamp = int(time.time())
        scripts = [
            (f"/tmp/remote_fetch_context_{timestamp}.py", REMOTE_PY),
            (f"/tmp/remote_fetch_context_db_{timestamp}.py", REMOTE_DB_PY),
        ]
        with client.open_sftp() as sftp:
            for path, body in scripts:
                with sftp.file(path, "w") as remote_file:
                    remote_file.write(body)
        commands = [
            f"cd /opt/telegram-alert-bot && ./.venv/bin/python {scripts[1][0]}; rm -f {scripts[1][0]}",
            f"cd /opt/telegram-alert-bot && ./.venv/bin/python {scripts[0][0]}; rm -f {scripts[0][0]}",
        ]
        for command in commands:
            print(f"\\n$ {command}")
            _stdin, stdout, stderr = client.exec_command(command, timeout=90)
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
