import os
import sys

import paramiko


HOST = "159.223.138.63"
USER = "root"


def main() -> int:
    password = os.getenv("SSH_PASSWORD")
    if not password:
        print("SSH_PASSWORD is required", file=sys.stderr)
        return 2
    commands = [
        "python3 - <<'PY'\n"
        "import urllib.request\n"
        "text = urllib.request.urlopen('https://159-223-138-63.sslip.io/admin/keywords', timeout=30).read().decode('utf-8')\n"
        "print('固定关键词' in text)\n"
        "print('请稍等-MAD' in text)\n"
        "print('已配置监控群' in text)\n"
        "PY",
        "systemctl is-active telegram-alert-bot",
        "systemctl is-active telegram-alert-listener",
    ]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=20)
    try:
        for command in commands:
            print(f"\n$ {command.splitlines()[0]}")
            _stdin, stdout, stderr = client.exec_command(command, timeout=60)
            code = stdout.channel.recv_exit_status()
            print(stdout.read().decode("utf-8", "replace"))
            err = stderr.read().decode("utf-8", "replace")
            if err:
                print(err, file=sys.stderr)
            print(f"exit {code}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
