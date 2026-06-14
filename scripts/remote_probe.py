import os
import sys

import paramiko


HOST = "159.223.138.63"
USER = "root"


COMMANDS = [
    "uname -a",
    "cat /etc/os-release | head -20",
    "command -v python3 || true",
    "python3 --version || true",
    "command -v redis-server || true",
    "systemctl is-active redis-server 2>/dev/null || systemctl is-active redis 2>/dev/null || true",
    "command -v nginx || true",
    "command -v caddy || true",
    "command -v certbot || true",
    "getent hosts 159-223-138-63.sslip.io || true",
    "ss -ltnp | grep -E ':80|:443|:6379|:8000' || true",
]


def main() -> int:
    password = os.getenv("SSH_PASSWORD")
    if not password:
        print("SSH_PASSWORD is required", file=sys.stderr)
        return 2
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=20)
    try:
        for command in COMMANDS:
            print(f"\n$ {command}")
            _stdin, stdout, stderr = client.exec_command(command, timeout=30)
            out = stdout.read().decode("utf-8", "replace").strip()
            err = stderr.read().decode("utf-8", "replace").strip()
            if out:
                print(out)
            if err:
                print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
