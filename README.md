# Telegram Alert Bot

FastAPI + aiogram service that monitors configured Telegram chats for fixed keywords, tracks quoted staff responses, and sends one private timeout alert to configured staff.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
Copy-Item .env.example .env
```

## Run

```powershell
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Test

```powershell
.\.venv\Scripts\pytest -q
```

## Pages

- Web admin: `/admin`
- Monitoring rules: `/admin/rules`
- Alert deliveries: `/admin/alerts`
- Telegram Mini App: `/mini`

## Zeabur Migration

Recommended server:

```text
Provider: Linode - Singapore
Plan: 1 vCPU / 2 GB RAM / 50 GB SSD
Runtime: Python 3.12 container
```

Create a Redis service in the same Zeabur project and set:

```text
REDIS_URL=<Zeabur Redis connection string>
SQLITE_PATH=/data/telegram_alert_bot.sqlite3
TELETHON_SESSION_PATH=/data/listener.session
WEBHOOK_URL=https://<new-zeabur-domain>/webhook/telegram
```

Copy these values from the existing deployment:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_API_ID
TELEGRAM_API_HASH
LISTENER_PHONE
ADMIN_PASSWORD
GLOBAL_TIMEOUT_MINUTES
```

After deployment, set the bot webhook:

```powershell
python scripts/set_telegram_webhook.py
```

Run the listener login once if `/data/listener.session` was not migrated:

```powershell
python scripts/listener_login.py
```

Do not shut down the old service until the new `/mini`, `/admin`, webhook, worker, and listener have been verified.
