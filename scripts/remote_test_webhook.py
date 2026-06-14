import json
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
    payload = {
        "update_id": 999,
        "message": {
            "message_id": 12345,
            "date": 1780588888,
            "chat": {"id": 7511822833, "title": "test-chat"},
            "from": {"id": 111, "username": "tester"},
            "text": "请稍等elk",
        },
    }
    command = (
        "python3 - <<'PY'\n"
        "import json, urllib.request\n"
        f"payload = {json.dumps(payload, ensure_ascii=False)!r}\n"
        "request = urllib.request.Request('https://159-223-138-63.sslip.io/webhook/telegram', data=payload.encode('utf-8'), headers={'Content-Type':'application/json'})\n"
        "print(urllib.request.urlopen(request, timeout=30).read().decode())\n"
        "PY\n"
        "redis-cli keys 'pending:*'\n"
        "redis-cli zrange timeout_queue 0 -1 withscores\n"
    )
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=20)
    try:
        _stdin, stdout, stderr = client.exec_command(command, timeout=60)
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
