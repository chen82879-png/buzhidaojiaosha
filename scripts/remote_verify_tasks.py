import os
import sys

import paramiko


HOST = "159.223.138.63"
USER = "root"


COMMAND = r"""
systemctl restart telegram-alert-listener
python3 - <<'PY'
import urllib.parse
import urllib.request

base = 'https://159-223-138-63.sslip.io'
today = urllib.request.urlopen(base + '/mini', timeout=30).read().decode('utf-8')
keywords = urllib.request.urlopen(base + '/mini/keywords', timeout=30).read().decode('utf-8')
print('mini_today_contains:', '任务' in today, '稍等 8M' in today, '跟进 15M' in today, '暂无任务' in today)
print('mini_keywords_form:', '保存名单' in keywords, 'name="enabled::请稍等elk"' in keywords, 'name="chat_ids::请稍等elk"' in keywords)
data = urllib.parse.urlencode({
    'enabled::请稍等elk': '1',
    'chat_ids::请稍等elk': '7511822833',
}).encode()
response = urllib.request.urlopen(
    urllib.request.Request(base + '/mini/keywords', data=data, method='POST'),
    timeout=30,
)
print('keyword_save_final_url:', response.geturl())
saved = urllib.request.urlopen(base + '/mini/keywords', timeout=30).read().decode('utf-8')
print('keyword_saved:', 'checked' in saved and '7511822833' in saved)
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
