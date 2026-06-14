import json
import os
import sys
import urllib.parse
import urllib.request


def telegram_api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")
    if not token or not webhook_url:
        print("TELEGRAM_BOT_TOKEN and WEBHOOK_URL are required.", file=sys.stderr)
        return 2

    parsed = urllib.parse.urlparse(webhook_url)
    if parsed.scheme != "https":
        print("WEBHOOK_URL must be an HTTPS URL for Telegram webhooks.", file=sys.stderr)
        return 2

    me = post_json(telegram_api_url(token, "getMe"), {})
    result = post_json(
        telegram_api_url(token, "setWebhook"),
        {
            "url": webhook_url,
            "allowed_updates": ["message", "channel_post"],
            "drop_pending_updates": False,
        },
    )
    info = post_json(telegram_api_url(token, "getWebhookInfo"), {})
    print(json.dumps({"me": me, "setWebhook": result, "webhookInfo": info}, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
