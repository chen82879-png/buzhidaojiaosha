import argparse
import os

from app.db import connect, migrate
from app.repositories import Repository


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Add an initial Telegram monitoring rule.")
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--chat-name", required=True)
    parser.add_argument("--keywords", required=True, help="Comma-separated fixed keywords.")
    parser.add_argument("--staff-user-id", required=True, type=int)
    parser.add_argument("--staff-username", default="")
    parser.add_argument("--staff-name", required=True)
    args = parser.parse_args()

    sqlite_path = os.getenv("SQLITE_PATH", "./data/telegram_alert_bot.sqlite3")
    conn = connect(sqlite_path)
    migrate(conn)
    repo = Repository(conn)
    rule_id = repo.create_monitor_rule(chat_id=args.chat_id, chat_name=args.chat_name, enabled=True)
    for keyword in parse_csv(args.keywords):
        repo.add_keyword(rule_id=rule_id, keyword=keyword, enabled=True)
    repo.add_staff(
        rule_id=rule_id,
        telegram_user_id=args.staff_user_id,
        telegram_username=args.staff_username.lstrip("@"),
        display_name=args.staff_name,
        enabled=True,
    )
    print(f"Created monitor rule {rule_id} for chat {args.chat_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
