import asyncio
import os
from pathlib import Path
import sys

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


async def main_async() -> int:
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    phone = os.getenv("LISTENER_PHONE", "")
    session_path = os.getenv("TELETHON_SESSION_PATH", "./data/listener.session")
    code = os.getenv("TELEGRAM_LOGIN_CODE", "")
    password = os.getenv("TELEGRAM_2FA_PASSWORD", "")
    hash_path = Path(f"{session_path}.phone_code_hash")
    if not api_id or not api_hash or not phone:
        print("TELEGRAM_API_ID, TELEGRAM_API_HASH, and LISTENER_PHONE are required.", file=sys.stderr)
        return 2

    client = TelegramClient(session_path, api_id, api_hash)
    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"authorized:{me.id}")
            return 0
        if not code:
            sent = await client.send_code_request(phone)
            hash_path.parent.mkdir(parents=True, exist_ok=True)
            hash_path.write_text(sent.phone_code_hash, encoding="utf-8")
            print(f"code_sent:{sent.phone_code_hash}")
            return 10
        phone_code_hash = os.getenv("TELEGRAM_PHONE_CODE_HASH", "")
        if not phone_code_hash and hash_path.exists():
            phone_code_hash = hash_path.read_text(encoding="utf-8").strip()
        if not phone_code_hash:
            print("phone_code_hash_required", file=sys.stderr)
            return 12
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                print("2fa_password_required", file=sys.stderr)
                return 11
            await client.sign_in(password=password)
        me = await client.get_me()
        print(f"authorized:{me.id}")
        return 0
    finally:
        await client.disconnect()


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
