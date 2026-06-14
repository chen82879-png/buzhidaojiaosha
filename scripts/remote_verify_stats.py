import os
import sys

import paramiko


HOST = "159.223.138.63"
USER = "root"


COMMAND = r"""
systemctl restart telegram-alert-listener
python3 - <<'PY'
import urllib.request

base = 'https://159-223-138-63.sslip.io'
today = urllib.request.urlopen(base + '/mini', timeout=30).read().decode('utf-8')
stats = urllib.request.urlopen(base + '/mini/me', timeout=30).read().decode('utf-8')
keywords = urllib.request.urlopen(base + '/mini/keywords', timeout=30).read().decode('utf-8')
print('today_nav_stats:', '统计' in today, '任务' in today)
print('stats_page_contains:', '统计' in stats, '固定关键词' in stats, '请稍等elk' in stats, '仅统计' in stats)
print('keywords_nav_stats:', '统计' in keywords, '稍等预警名单' in keywords)
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
