import os
import posixpath
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko


HOST = "159.223.138.63"
USER = "root"
DOMAIN = "159-223-138-63.sslip.io"
REMOTE_DIR = "/opt/telegram-alert-bot"
SERVICE_NAME = "telegram-alert-bot"


INCLUDE_PATHS = [
    "app",
    "scripts/add_monitor_rule.py",
    "scripts/listener_login.py",
    "scripts/set_telegram_webhook.py",
    "pyproject.toml",
    "README.md",
]


def run(client: paramiko.SSHClient, command: str, timeout: int = 300) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return code, out, err


def must_run(client: paramiko.SSHClient, command: str, timeout: int = 300) -> str:
    code, out, err = run(client, command, timeout)
    if code != 0:
        raise RuntimeError(f"Command failed ({code}): {command}\nSTDOUT:\n{out}\nSTDERR:\n{err}")
    return out


def make_archive(root: Path) -> Path:
    tmp = Path(tempfile.gettempdir()) / "telegram-alert-bot-deploy.tar.gz"
    if tmp.exists():
        tmp.unlink()
    with tarfile.open(tmp, "w:gz") as tar:
        for rel in INCLUDE_PATHS:
            path = root / rel
            tar.add(path, arcname=rel)
    return tmp


def upload_archive(client: paramiko.SSHClient, archive: Path) -> None:
    sftp = client.open_sftp()
    try:
        sftp.put(str(archive), "/tmp/telegram-alert-bot-deploy.tar.gz")
    finally:
        sftp.close()


def write_remote_file(client: paramiko.SSHClient, path: str, content: str, mode: str = "0644") -> None:
    encoded = content.encode("utf-8")
    tmp_path = f"/tmp/{posixpath.basename(path)}.tmp"
    sftp = client.open_sftp()
    try:
        with sftp.file(tmp_path, "wb") as handle:
            handle.write(encoded)
    finally:
        sftp.close()
    must_run(client, f"install -m {mode} {tmp_path} {path} && rm -f {tmp_path}")


def main() -> int:
    password = os.getenv("SSH_PASSWORD")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    api_id = os.getenv("TELEGRAM_API_ID", "")
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    listener_phone = os.getenv("LISTENER_PHONE", "")
    if not password or not bot_token:
        print("SSH_PASSWORD and TELEGRAM_BOT_TOKEN are required", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    archive = make_archive(root)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=20)
    try:
        print("Uploading project archive...")
        upload_archive(client, archive)

        print("Preparing application directory...")
        must_run(
            client,
            f"mkdir -p {REMOTE_DIR} /var/lib/telegram-alert-bot && "
            f"tar -xzf /tmp/telegram-alert-bot-deploy.tar.gz -C {REMOTE_DIR} && "
            f"rm -f /tmp/telegram-alert-bot-deploy.tar.gz",
        )

        env_content = "\n".join(
            [
                f"TELEGRAM_BOT_TOKEN={bot_token}",
                f"WEBHOOK_URL=https://{DOMAIN}/webhook/telegram",
                "REDIS_URL=redis://127.0.0.1:6379/0",
                "SQLITE_PATH=/var/lib/telegram-alert-bot/telegram_alert_bot.sqlite3",
                "ADMIN_PASSWORD=change-me",
                "GLOBAL_TIMEOUT_MINUTES=15",
                f"TELEGRAM_API_ID={api_id}",
                f"TELEGRAM_API_HASH={api_hash}",
                f"LISTENER_PHONE={listener_phone}",
                "TELETHON_SESSION_PATH=/var/lib/telegram-alert-bot/listener",
                "",
            ]
        )
        write_remote_file(client, f"{REMOTE_DIR}/.env", env_content, "0600")

        print("Installing Python environment...")
        must_run(
            client,
            "apt-get update && apt-get install -y python3-venv",
            timeout=600,
        )
        must_run(
            client,
            f"cd {REMOTE_DIR} && python3 -m venv .venv && "
            f".venv/bin/pip install --upgrade pip && .venv/bin/pip install -e .",
            timeout=900,
        )

        service = f"""[Unit]
Description=Telegram Alert Bot
After=network-online.target redis-server.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={REMOTE_DIR}
EnvironmentFile={REMOTE_DIR}/.env
ExecStart={REMOTE_DIR}/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
        write_remote_file(client, f"/etc/systemd/system/{SERVICE_NAME}.service", service)

        listener_service = f"""[Unit]
Description=Telegram Alert Listener Account
After=network-online.target redis-server.service {SERVICE_NAME}.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={REMOTE_DIR}
EnvironmentFile={REMOTE_DIR}/.env
ExecStart={REMOTE_DIR}/.venv/bin/python -m app.listener
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
        write_remote_file(client, "/etc/systemd/system/telegram-alert-listener.service", listener_service)

        print("Configuring Caddy...")
        caddy_block = f"""{DOMAIN} {{
    reverse_proxy 127.0.0.1:8000
}}
"""
        escaped_block = caddy_block.replace("'", "'\"'\"'")
        must_run(
            client,
            "cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.telegram-alert-bot.bak 2>/dev/null || true",
        )
        must_run(
            client,
            f"python3 - <<'PY'\n"
            f"from pathlib import Path\n"
            f"path = Path('/etc/caddy/Caddyfile')\n"
            f"text = path.read_text() if path.exists() else ''\n"
            f"domain = '{DOMAIN}'\n"
            f"block = '''{escaped_block}'''\n"
            f"if domain not in text:\n"
            f"    if text and not text.endswith('\\n'):\n"
            f"        text += '\\n'\n"
            f"    text += '\\n' + block\n"
            f"    path.write_text(text)\n"
            f"PY"
        )
        must_run(client, "systemctl daemon-reload && systemctl enable telegram-alert-bot telegram-alert-listener")
        must_run(client, "systemctl restart telegram-alert-bot")
        must_run(client, "caddy validate --config /etc/caddy/Caddyfile")
        must_run(client, "systemctl reload caddy")

        print("Registering Telegram webhook...")
        out = must_run(
            client,
            f"cd {REMOTE_DIR} && set -a && . ./.env && set +a && .venv/bin/python scripts/set_telegram_webhook.py",
            timeout=120,
        )
        print(out)

        print("Checking service and endpoint...")
        print(must_run(client, "systemctl is-active telegram-alert-bot"))
        print(must_run(client, f"curl -fsS https://{DOMAIN}/admin | head -5", timeout=120))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
