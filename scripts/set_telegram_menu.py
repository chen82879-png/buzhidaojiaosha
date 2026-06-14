import json
import os
import sys
import urllib.request


def post_json(token: str, method: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    miniapp_url = os.getenv("TELEGRAM_MINIAPP_URL")
    if not token or not miniapp_url:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_MINIAPP_URL are required.", file=sys.stderr)
        return 2
    result = post_json(
        token,
        "setChatMenuButton",
        {
            "menu_button": {
                "type": "web_app",
                "text": "预警面板",
                "web_app": {"url": miniapp_url},
            }
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
