import os
import sys

import paramiko


HOST = "159.223.138.63"
USER = "root"


COMMAND = r"""
python3 - <<'PY'
import urllib.request

text = urllib.request.urlopen('https://159-223-138-63.sslip.io/mini/keywords', timeout=30).read().decode('utf-8')
print(
    'mini_keywords_contains:',
    '稍等预警名单' in text,
    '保存名单' in text,
    '接收人 Chat ID' in text,
    '请稍等-MAD' in text,
    'mini-body' in text,
    'mini-tabs' in text,
)
print(
    'configured_groups_hidden:',
    '启用群组' not in text,
    '9-YY-DL对接' not in text,
    '-1001571955528' not in text,
)
response = urllib.request.urlopen('https://159-223-138-63.sslip.io/admin/keywords', timeout=30)
print('admin_keywords_final_url:', response.geturl())
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
