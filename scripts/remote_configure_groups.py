import os
import sys
import textwrap

import paramiko


HOST = "159.223.138.63"
USER = "root"

GROUP_NAMES = [
    "9-YY-F1TG对接",
    "9-YY-F2TG对接",
    "9-YY-JPZTG对接",
    "9-YYCP 反馈",
    "9-YY-ZX8&ZX2 对接",
    "9-YY-WH1对接",
    "9-YY-WH2对接",
    "9-YY-WH3对接",
    "9-YY-DL对接",
    "【ML】DL-运营对接群",
    "9-YY-AFF对接",
]


REMOTE_SCRIPT = r'''
import asyncio
import os
import sqlite3

from telethon import TelegramClient

GROUP_NAMES = __GROUP_NAMES__
KEYWORD = os.getenv("MONITOR_KEYWORD", "请稍等elk")
STAFF_USER_ID = int(os.getenv("STAFF_USER_ID", "7511822833"))
STAFF_NAME = os.getenv("STAFF_NAME", "test-staff")


def ensure_rule(conn, chat_id, chat_name):
    row = conn.execute("select id from monitor_rules where chat_id = ?", (chat_id,)).fetchone()
    if row:
        rule_id = row[0]
        conn.execute(
            "update monitor_rules set chat_name = ?, enabled = 1, updated_at = CURRENT_TIMESTAMP where id = ?",
            (chat_name, rule_id),
        )
    else:
        cur = conn.execute(
            "insert into monitor_rules(chat_id, chat_name, enabled) values (?, ?, 1)",
            (chat_id, chat_name),
        )
        rule_id = cur.lastrowid

    conn.execute(
        """
        insert into rule_keywords(rule_id, keyword, enabled, note)
        values (?, ?, 1, '')
        on conflict(rule_id, keyword) do update set enabled = 1, updated_at = CURRENT_TIMESTAMP
        """,
        (rule_id, KEYWORD),
    )
    conn.execute(
        """
        insert into rule_staff(rule_id, telegram_user_id, telegram_username, display_name, enabled)
        values (?, ?, '', ?, 1)
        on conflict(rule_id, telegram_user_id) do update set display_name = excluded.display_name, enabled = 1, updated_at = CURRENT_TIMESTAMP
        """,
        (rule_id, STAFF_USER_ID, STAFF_NAME),
    )
    return rule_id


async def main():
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session_path = os.environ["TELETHON_SESSION_PATH"]
    sqlite_path = os.environ["SQLITE_PATH"]
    client = TelegramClient(session_path, api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("listener account is not authorized")

    wanted = {name.casefold(): name for name in GROUP_NAMES}
    found = {}
    async for dialog in client.iter_dialogs():
        title = dialog.name or ""
        key = title.casefold()
        if key in wanted:
            found[wanted[key]] = str(dialog.id)

    conn = sqlite3.connect(sqlite_path)
    try:
        for name in GROUP_NAMES:
            chat_id = found.get(name)
            if chat_id:
                rule_id = ensure_rule(conn, chat_id, name)
                print(f"FOUND\t{rule_id}\t{chat_id}\t{name}")
            else:
                print(f"MISSING\t-\t-\t{name}")
        conn.commit()
    finally:
        conn.close()
        await client.disconnect()


asyncio.run(main())
'''


def main() -> int:
    password = os.getenv("SSH_PASSWORD")
    if not password:
        print("SSH_PASSWORD is required", file=sys.stderr)
        return 2

    remote_script = REMOTE_SCRIPT.replace("__GROUP_NAMES__", repr(GROUP_NAMES))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=20)
    try:
        sftp = client.open_sftp()
        try:
            with sftp.file("/tmp/configure_telegram_groups.py", "w") as handle:
                handle.write(remote_script)
        finally:
            sftp.close()
        command = textwrap.dedent(
            """
            cd /opt/telegram-alert-bot &&
            set -a && . ./.env && set +a &&
            MONITOR_KEYWORD='请稍等elk' STAFF_USER_ID='7511822833' STAFF_NAME='test-staff' \
            .venv/bin/python /tmp/configure_telegram_groups.py
            """
        ).strip()
        _stdin, stdout, stderr = client.exec_command(command, timeout=120)
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
