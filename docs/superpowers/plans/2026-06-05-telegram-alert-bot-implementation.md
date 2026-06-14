# Telegram Alert Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram alert bot with fixed keyword monitoring, Redis-backed timeout tracking, one-time private staff alerts, keyword hit statistics, a web admin console, and a Telegram Mini App staff view.

**Architecture:** Create a Python FastAPI monolith with focused internal modules. SQLite stores configuration, statistics, and alert delivery audit records; Redis stores pending monitored messages, timeout queue entries, and alert de-duplication keys. Web admin and Mini App pages are served by FastAPI with static HTML/CSS/JS in the first version.

**Tech Stack:** Python 3.12, FastAPI, aiogram, SQLite, redis-py, pytest, pytest-asyncio, httpx, Jinja2, vanilla HTML/CSS/JS, Lucide-style SVG icons.

---

## File Structure

- Create: `pyproject.toml` - project metadata, dependencies, pytest configuration.
- Create: `.env.example` - required runtime environment variables.
- Create: `.gitignore` - ignore local databases, virtualenvs, caches, and `.superpowers`.
- Create: `README.md` - setup, run, and Telegram webhook instructions.
- Create: `app/__init__.py` - package marker.
- Create: `app/config.py` - environment loading and settings object.
- Create: `app/db.py` - SQLite connection helper and schema migration function.
- Create: `app/models.py` - dataclasses for rules, keywords, staff, hits, pending messages, and alert records.
- Create: `app/repositories.py` - SQLite repository methods for rules, keywords, staff, hits, settings, and alert deliveries.
- Create: `app/redis_queue.py` - Redis pending message, timeout queue, and alert de-duplication operations.
- Create: `app/telegram_utils.py` - Telegram message URL generation and normalized message helpers.
- Create: `app/matcher.py` - chat/rule/keyword matching logic.
- Create: `app/response_detector.py` - staff quoted-reply response detection.
- Create: `app/alerts.py` - alert template rendering and Telegram private-message sending wrapper.
- Create: `app/worker.py` - timeout scanning and one-time alert workflow.
- Create: `app/bot.py` - aiogram update handling for incoming messages.
- Create: `app/main.py` - FastAPI app, webhook endpoint, admin routes, Mini App routes.
- Create: `app/templates/base.html` - shared page shell.
- Create: `app/templates/admin_stats.html` - statistics overview.
- Create: `app/templates/admin_rules.html` - monitoring rule configuration.
- Create: `app/templates/admin_alerts.html` - alert delivery records.
- Create: `app/templates/mini_today.html` - Mini App today tab.
- Create: `app/templates/mini_rules.html` - Mini App rules tab.
- Create: `app/templates/mini_me.html` - Mini App identity tab.
- Create: `app/static/styles.css` - design system, layouts, components, responsive behavior.
- Create: `app/static/admin.js` - admin forms, keyword import preview, loading states.
- Create: `app/static/miniapp.js` - Telegram Mini App initialization, copy/open actions.
- Create: `tests/conftest.py` - temporary SQLite DB, fake Redis, fake Telegram bot fixtures.
- Create: `tests/test_matcher.py` - rule and keyword matching tests.
- Create: `tests/test_redis_queue.py` - pending message, timeout queue, and de-dup tests.
- Create: `tests/test_response_detector.py` - quoted staff reply tests.
- Create: `tests/test_worker.py` - timeout alert and one-time delivery tests.
- Create: `tests/test_repositories.py` - SQLite persistence and statistics aggregation tests.
- Create: `tests/test_telegram_utils.py` - Telegram URL generation tests.
- Create: `tests/test_admin_routes.py` - web admin API/page smoke tests.
- Create: `tests/test_miniapp_routes.py` - Mini App page smoke tests.

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`
- Create: `app/__init__.py`

- [ ] **Step 1: Create project metadata**

Write `pyproject.toml`:

```toml
[project]
name = "telegram-alert-bot"
version = "0.1.0"
description = "Telegram keyword timeout alert bot"
requires-python = ">=3.12"
dependencies = [
  "aiogram>=3.7,<4",
  "fastapi>=0.111,<1",
  "uvicorn[standard]>=0.30,<1",
  "redis>=5,<6",
  "jinja2>=3.1,<4",
  "python-multipart>=0.0.9,<1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "pytest-asyncio>=0.23,<1",
  "httpx>=0.27,<1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create environment example**

Write `.env.example`:

```text
TELEGRAM_BOT_TOKEN=123456:replace-me
WEBHOOK_URL=https://example.com/webhook/telegram
REDIS_URL=redis://127.0.0.1:6379/0
SQLITE_PATH=./data/telegram_alert_bot.sqlite3
ADMIN_PASSWORD=change-me
GLOBAL_TIMEOUT_MINUTES=15
```

- [ ] **Step 3: Create ignore rules**

Write `.gitignore`:

```text
.venv/
__pycache__/
.pytest_cache/
*.pyc
.env
data/
.superpowers/
```

- [ ] **Step 4: Create README**

Write `README.md`:

````markdown
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
````

- [ ] **Step 5: Add package marker**

Write `app/__init__.py` as an empty file.

- [ ] **Step 6: Verify scaffold**

Run: `python -m pytest -q`

Expected before test files exist: pytest exits with no tests collected or reports the empty test suite. If dependencies are not installed yet, install development dependencies first.

- [ ] **Step 7: Commit**

Run if `git` is available:

```bash
git add pyproject.toml .env.example .gitignore README.md app/__init__.py
git commit -m "chore: scaffold telegram alert bot"
```

If `git` is unavailable, record the skipped commit in the final implementation note.

---

### Task 2: Configuration, Models, and SQLite Schema

**Files:**
- Create: `app/config.py`
- Create: `app/models.py`
- Create: `app/db.py`
- Create: `tests/test_repositories.py`
- Create: `app/repositories.py`

- [ ] **Step 1: Write failing schema test**

Create `tests/test_repositories.py`:

```python
from datetime import datetime, timezone

from app.db import connect, migrate
from app.repositories import Repository


def test_migrate_creates_rule_keyword_staff_and_hit_records(tmp_path):
    db_path = tmp_path / "app.sqlite3"
    conn = connect(str(db_path))
    migrate(conn)
    repo = Repository(conn)

    rule_id = repo.create_monitor_rule(chat_id="-1001571955528", chat_name="Ops Group", enabled=True)
    repo.add_keyword(rule_id=rule_id, keyword="充值", enabled=True, note="payment")
    repo.add_staff(
        rule_id=rule_id,
        telegram_user_id=9001,
        telegram_username="ML_YYZB3",
        display_name="YY_6/9_值班号3",
        enabled=True,
    )
    repo.record_keyword_hit(
        rule_id=rule_id,
        chat_id="-1001571955528",
        chat_name="Ops Group",
        message_id=398744,
        telegram_user_id=10001,
        telegram_username="customer_a",
        matched_keyword="充值",
        message_excerpt="充值失败",
        message_url="https://t.me/c/1571955528/398744",
        message_time=datetime(2026, 6, 4, 21, 11, 25, tzinfo=timezone.utc),
    )

    rules = repo.list_enabled_rules()
    stats = repo.keyword_hit_counts()

    assert rules[0].chat_id == "-1001571955528"
    assert rules[0].keywords[0].keyword == "充值"
    assert rules[0].staff[0].telegram_username == "ML_YYZB3"
    assert stats[0]["matched_keyword"] == "充值"
    assert stats[0]["count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repositories.py::test_migrate_creates_rule_keyword_staff_and_hit_records -q`

Expected: FAIL because `app.db` and `app.repositories` do not exist.

- [ ] **Step 3: Implement config and models**

Write `app/config.py`:

```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    webhook_url: str
    redis_url: str
    sqlite_path: str
    admin_password: str
    global_timeout_minutes: int


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        webhook_url=os.getenv("WEBHOOK_URL", ""),
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        sqlite_path=os.getenv("SQLITE_PATH", "./data/telegram_alert_bot.sqlite3"),
        admin_password=os.getenv("ADMIN_PASSWORD", "change-me"),
        global_timeout_minutes=int(os.getenv("GLOBAL_TIMEOUT_MINUTES", "15")),
    )
```

Write `app/models.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RuleKeyword:
    id: int
    rule_id: int
    keyword: str
    enabled: bool
    note: str


@dataclass(frozen=True)
class RuleStaff:
    id: int
    rule_id: int
    telegram_user_id: int
    telegram_username: str
    display_name: str
    enabled: bool


@dataclass(frozen=True)
class MonitorRule:
    id: int
    chat_id: str
    chat_name: str
    enabled: bool
    keywords: list[RuleKeyword] = field(default_factory=list)
    staff: list[RuleStaff] = field(default_factory=list)


@dataclass(frozen=True)
class PendingMessage:
    rule_id: int
    chat_id: str
    chat_name: str
    message_id: int
    message_time: datetime
    matched_keywords: list[str]
    message_excerpt: str
    message_url: str
    status: str = "pending"
```

- [ ] **Step 4: Implement SQLite migration and repository**

Write `app/db.py`:

```python
import sqlite3
from pathlib import Path


def connect(sqlite_path: str) -> sqlite3.Connection:
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS monitor_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL UNIQUE,
            chat_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rule_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL REFERENCES monitor_rules(id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rule_id, keyword)
        );
        CREATE TABLE IF NOT EXISTS rule_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL REFERENCES monitor_rules(id) ON DELETE CASCADE,
            telegram_user_id INTEGER NOT NULL,
            telegram_username TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rule_id, telegram_user_id)
        );
        CREATE TABLE IF NOT EXISTS keyword_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL REFERENCES monitor_rules(id) ON DELETE CASCADE,
            chat_id TEXT NOT NULL,
            chat_name TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            telegram_user_id INTEGER NOT NULL,
            telegram_username TEXT NOT NULL DEFAULT '',
            matched_keyword TEXT NOT NULL,
            message_excerpt TEXT NOT NULL,
            message_url TEXT NOT NULL,
            message_time TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS alert_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            matched_keyword TEXT NOT NULL,
            staff_telegram_user_id INTEGER NOT NULL,
            staff_telegram_username TEXT NOT NULL,
            staff_display_name TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT NOT NULL DEFAULT '',
            sent_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
```

Write `app/repositories.py`:

```python
import sqlite3
from datetime import datetime

from app.models import MonitorRule, RuleKeyword, RuleStaff


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_monitor_rule(self, chat_id: str, chat_name: str, enabled: bool) -> int:
        cur = self.conn.execute(
            "INSERT INTO monitor_rules(chat_id, chat_name, enabled) VALUES (?, ?, ?)",
            (chat_id, chat_name, int(enabled)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_keyword(self, rule_id: int, keyword: str, enabled: bool, note: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO rule_keywords(rule_id, keyword, enabled, note) VALUES (?, ?, ?, ?)",
            (rule_id, keyword, int(enabled), note),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_staff(
        self,
        rule_id: int,
        telegram_user_id: int,
        telegram_username: str,
        display_name: str,
        enabled: bool,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO rule_staff(rule_id, telegram_user_id, telegram_username, display_name, enabled)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rule_id, telegram_user_id, telegram_username, display_name, int(enabled)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_enabled_rules(self) -> list[MonitorRule]:
        rule_rows = self.conn.execute(
            "SELECT id, chat_id, chat_name, enabled FROM monitor_rules WHERE enabled = 1 ORDER BY id"
        ).fetchall()
        rules: list[MonitorRule] = []
        for row in rule_rows:
            keyword_rows = self.conn.execute(
                "SELECT id, rule_id, keyword, enabled, note FROM rule_keywords WHERE rule_id = ? ORDER BY id",
                (row["id"],),
            ).fetchall()
            staff_rows = self.conn.execute(
                """
                SELECT id, rule_id, telegram_user_id, telegram_username, display_name, enabled
                FROM rule_staff WHERE rule_id = ? ORDER BY id
                """,
                (row["id"],),
            ).fetchall()
            rules.append(
                MonitorRule(
                    id=row["id"],
                    chat_id=row["chat_id"],
                    chat_name=row["chat_name"],
                    enabled=bool(row["enabled"]),
                    keywords=[
                        RuleKeyword(
                            id=k["id"],
                            rule_id=k["rule_id"],
                            keyword=k["keyword"],
                            enabled=bool(k["enabled"]),
                            note=k["note"],
                        )
                        for k in keyword_rows
                    ],
                    staff=[
                        RuleStaff(
                            id=s["id"],
                            rule_id=s["rule_id"],
                            telegram_user_id=s["telegram_user_id"],
                            telegram_username=s["telegram_username"],
                            display_name=s["display_name"],
                            enabled=bool(s["enabled"]),
                        )
                        for s in staff_rows
                    ],
                )
            )
        return rules

    def record_keyword_hit(
        self,
        rule_id: int,
        chat_id: str,
        chat_name: str,
        message_id: int,
        telegram_user_id: int,
        telegram_username: str,
        matched_keyword: str,
        message_excerpt: str,
        message_url: str,
        message_time: datetime,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO keyword_hits(
                rule_id, chat_id, chat_name, message_id, telegram_user_id, telegram_username,
                matched_keyword, message_excerpt, message_url, message_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                chat_id,
                chat_name,
                message_id,
                telegram_user_id,
                telegram_username,
                matched_keyword,
                message_excerpt,
                message_url,
                message_time.isoformat(),
            ),
        )
        self.conn.commit()

    def keyword_hit_counts(self) -> list[dict[str, object]]:
        rows = self.conn.execute(
            """
            SELECT matched_keyword, COUNT(*) AS count
            FROM keyword_hits
            GROUP BY matched_keyword
            ORDER BY count DESC, matched_keyword
            """
        ).fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_repositories.py::test_migrate_creates_rule_keyword_staff_and_hit_records -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run if `git` is available:

```bash
git add app/config.py app/models.py app/db.py app/repositories.py tests/test_repositories.py
git commit -m "feat: add sqlite configuration storage"
```

---

### Task 3: Telegram URL Generation and Rule Matching

**Files:**
- Create: `tests/test_telegram_utils.py`
- Create: `tests/test_matcher.py`
- Create: `app/telegram_utils.py`
- Create: `app/matcher.py`

- [ ] **Step 1: Write failing URL tests**

Create `tests/test_telegram_utils.py`:

```python
from app.telegram_utils import build_message_url


def test_builds_private_supergroup_message_url():
    assert build_message_url(chat_id="-1001571955528", message_id=398744, username="") == (
        "https://t.me/c/1571955528/398744"
    )


def test_builds_public_chat_message_url():
    assert build_message_url(chat_id="-100111", message_id=42, username="public_ops") == (
        "https://t.me/public_ops/42"
    )
```

- [ ] **Step 2: Write failing matcher tests**

Create `tests/test_matcher.py`:

```python
from app.matcher import match_message
from app.models import MonitorRule, RuleKeyword, RuleStaff


def test_disabled_chat_rule_is_ignored():
    rule = MonitorRule(
        id=1,
        chat_id="-1001",
        chat_name="Ops",
        enabled=False,
        keywords=[RuleKeyword(id=1, rule_id=1, keyword="充值", enabled=True, note="")],
        staff=[],
    )

    assert match_message(chat_id="-1001", text="充值失败", rules=[rule]) is None


def test_enabled_chat_and_keyword_returns_matched_keywords():
    rule = MonitorRule(
        id=1,
        chat_id="-1001",
        chat_name="Ops",
        enabled=True,
        keywords=[
            RuleKeyword(id=1, rule_id=1, keyword="充值", enabled=True, note=""),
            RuleKeyword(id=2, rule_id=1, keyword="失败", enabled=True, note=""),
        ],
        staff=[RuleStaff(id=1, rule_id=1, telegram_user_id=9001, telegram_username="agent", display_name="Agent", enabled=True)],
    )

    result = match_message(chat_id="-1001", text="充值失败，请处理", rules=[rule])

    assert result is not None
    assert result.rule.id == 1
    assert result.matched_keywords == ["充值", "失败"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_telegram_utils.py tests/test_matcher.py -q`

Expected: FAIL because `app.telegram_utils` and `app.matcher` do not exist.

- [ ] **Step 4: Implement URL and matcher modules**

Write `app/telegram_utils.py`:

```python
def build_message_url(chat_id: str, message_id: int, username: str = "") -> str:
    if username:
        return f"https://t.me/{username}/{message_id}"
    internal_id = chat_id
    if internal_id.startswith("-100"):
        internal_id = internal_id[4:]
    elif internal_id.startswith("-"):
        internal_id = internal_id[1:]
    return f"https://t.me/c/{internal_id}/{message_id}"
```

Write `app/matcher.py`:

```python
from dataclasses import dataclass

from app.models import MonitorRule


@dataclass(frozen=True)
class MatchResult:
    rule: MonitorRule
    matched_keywords: list[str]


def match_message(chat_id: str, text: str, rules: list[MonitorRule]) -> MatchResult | None:
    for rule in rules:
        if not rule.enabled or rule.chat_id != chat_id:
            continue
        matched = [keyword.keyword for keyword in rule.keywords if keyword.enabled and keyword.keyword in text]
        if matched:
            return MatchResult(rule=rule, matched_keywords=matched)
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_telegram_utils.py tests/test_matcher.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run if `git` is available:

```bash
git add app/telegram_utils.py app/matcher.py tests/test_telegram_utils.py tests/test_matcher.py
git commit -m "feat: match monitored telegram keywords"
```

---

### Task 4: Redis Pending Queue

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_redis_queue.py`
- Create: `app/redis_queue.py`

- [ ] **Step 1: Write fake Redis fixture**

Create `tests/conftest.py`:

```python
import pytest


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.sorted_sets = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, key):
        existed = key in self.values
        self.values.pop(key, None)
        return int(existed)

    async def zadd(self, name, mapping):
        self.sorted_sets.setdefault(name, {}).update(mapping)
        return len(mapping)

    async def zrangebyscore(self, name, min_score, max_score, start=0, num=None):
        items = [
            member for member, score in self.sorted_sets.get(name, {}).items()
            if float(min_score) <= score <= float(max_score)
        ]
        items.sort(key=lambda member: self.sorted_sets[name][member])
        if num is None:
            return items[start:]
        return items[start:start + num]

    async def zrem(self, name, *members):
        count = 0
        for member in members:
            if member in self.sorted_sets.get(name, {}):
                del self.sorted_sets[name][member]
                count += 1
        return count


@pytest.fixture
def fake_redis():
    return FakeRedis()
```

- [ ] **Step 2: Write failing queue tests**

Create `tests/test_redis_queue.py`:

```python
from datetime import datetime, timezone

from app.models import PendingMessage
from app.redis_queue import RedisQueue


async def test_adds_pending_message_and_due_timeout(fake_redis):
    queue = RedisQueue(fake_redis)
    pending = PendingMessage(
        rule_id=1,
        chat_id="-1001571955528",
        chat_name="Ops",
        message_id=398744,
        message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        matched_keywords=["充值"],
        message_excerpt="充值失败",
        message_url="https://t.me/c/1571955528/398744",
    )

    await queue.add_pending(pending, due_at=1000)
    loaded = await queue.get_pending("-1001571955528", 398744)
    due = await queue.due_members(now_timestamp=1000)

    assert loaded == pending
    assert due == ["-1001571955528:398744"]


async def test_alert_dedupe_only_allows_first_mark(fake_redis):
    queue = RedisQueue(fake_redis)

    assert await queue.mark_alerted("-1001", 10) is True
    assert await queue.mark_alerted("-1001", 10) is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_redis_queue.py -q`

Expected: FAIL because `app.redis_queue` does not exist.

- [ ] **Step 4: Implement Redis queue**

Write `app/redis_queue.py`:

```python
import json
from datetime import datetime

from app.models import PendingMessage


class RedisQueue:
    def __init__(self, redis_client):
        self.redis = redis_client

    @staticmethod
    def pending_key(chat_id: str, message_id: int) -> str:
        return f"pending:{chat_id}:{message_id}"

    @staticmethod
    def member(chat_id: str, message_id: int) -> str:
        return f"{chat_id}:{message_id}"

    @staticmethod
    def alerted_key(chat_id: str, message_id: int) -> str:
        return f"alerted:{chat_id}:{message_id}"

    async def add_pending(self, pending: PendingMessage, due_at: float) -> None:
        payload = {
            "rule_id": pending.rule_id,
            "chat_id": pending.chat_id,
            "chat_name": pending.chat_name,
            "message_id": pending.message_id,
            "message_time": pending.message_time.isoformat(),
            "matched_keywords": pending.matched_keywords,
            "message_excerpt": pending.message_excerpt,
            "message_url": pending.message_url,
            "status": pending.status,
        }
        await self.redis.set(self.pending_key(pending.chat_id, pending.message_id), json.dumps(payload, ensure_ascii=False))
        await self.redis.zadd("timeout_queue", {self.member(pending.chat_id, pending.message_id): due_at})

    async def get_pending(self, chat_id: str, message_id: int) -> PendingMessage | None:
        raw = await self.redis.get(self.pending_key(chat_id, message_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return PendingMessage(
            rule_id=data["rule_id"],
            chat_id=data["chat_id"],
            chat_name=data["chat_name"],
            message_id=data["message_id"],
            message_time=datetime.fromisoformat(data["message_time"]),
            matched_keywords=list(data["matched_keywords"]),
            message_excerpt=data["message_excerpt"],
            message_url=data["message_url"],
            status=data["status"],
        )

    async def close_pending(self, chat_id: str, message_id: int) -> None:
        await self.redis.delete(self.pending_key(chat_id, message_id))
        await self.redis.zrem("timeout_queue", self.member(chat_id, message_id))

    async def due_members(self, now_timestamp: float, limit: int = 100) -> list[str]:
        return await self.redis.zrangebyscore("timeout_queue", 0, now_timestamp, start=0, num=limit)

    async def remove_member(self, member: str) -> None:
        await self.redis.zrem("timeout_queue", member)

    async def mark_alerted(self, chat_id: str, message_id: int) -> bool:
        return bool(await self.redis.set(self.alerted_key(chat_id, message_id), "1", nx=True))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_redis_queue.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run if `git` is available:

```bash
git add app/redis_queue.py tests/conftest.py tests/test_redis_queue.py
git commit -m "feat: add redis timeout queue"
```

---

### Task 5: Response Detection

**Files:**
- Create: `tests/test_response_detector.py`
- Create: `app/response_detector.py`

- [ ] **Step 1: Write failing response detection tests**

Create `tests/test_response_detector.py`:

```python
from app.models import MonitorRule, RuleKeyword, RuleStaff
from app.response_detector import IncomingMessage, detect_staff_response


def test_staff_quoted_reply_closes_pending_message():
    rule = MonitorRule(
        id=1,
        chat_id="-1001",
        chat_name="Ops",
        enabled=True,
        keywords=[RuleKeyword(id=1, rule_id=1, keyword="充值", enabled=True, note="")],
        staff=[RuleStaff(id=1, rule_id=1, telegram_user_id=9001, telegram_username="agent", display_name="Agent", enabled=True)],
    )
    message = IncomingMessage(chat_id="-1001", sender_user_id=9001, message_id=51, reply_to_message_id=50)

    assert detect_staff_response(message, [rule]) == ("-1001", 50)


def test_staff_non_reply_does_not_close_pending_message():
    rule = MonitorRule(
        id=1,
        chat_id="-1001",
        chat_name="Ops",
        enabled=True,
        keywords=[],
        staff=[RuleStaff(id=1, rule_id=1, telegram_user_id=9001, telegram_username="agent", display_name="Agent", enabled=True)],
    )
    message = IncomingMessage(chat_id="-1001", sender_user_id=9001, message_id=51, reply_to_message_id=None)

    assert detect_staff_response(message, [rule]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_response_detector.py -q`

Expected: FAIL because `app.response_detector` does not exist.

- [ ] **Step 3: Implement response detector**

Write `app/response_detector.py`:

```python
from dataclasses import dataclass

from app.models import MonitorRule


@dataclass(frozen=True)
class IncomingMessage:
    chat_id: str
    sender_user_id: int
    message_id: int
    reply_to_message_id: int | None


def detect_staff_response(message: IncomingMessage, rules: list[MonitorRule]) -> tuple[str, int] | None:
    if message.reply_to_message_id is None:
        return None
    for rule in rules:
        if not rule.enabled or rule.chat_id != message.chat_id:
            continue
        staff_ids = {staff.telegram_user_id for staff in rule.staff if staff.enabled}
        if message.sender_user_id in staff_ids:
            return (message.chat_id, message.reply_to_message_id)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_response_detector.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run if `git` is available:

```bash
git add app/response_detector.py tests/test_response_detector.py
git commit -m "feat: detect quoted staff responses"
```

---

### Task 6: Alert Rendering and Timeout Worker

**Files:**
- Create: `tests/test_worker.py`
- Create: `app/alerts.py`
- Create: `app/worker.py`
- Modify: `app/repositories.py`

- [ ] **Step 1: Write failing timeout worker tests**

Create `tests/test_worker.py`:

```python
from datetime import datetime, timezone

from app.models import MonitorRule, PendingMessage, RuleStaff
from app.redis_queue import RedisQueue
from app.worker import TimeoutWorker


class FakeAlertSender:
    def __init__(self):
        self.sent = []

    async def send_timeout_alert(self, staff, pending, timeout_minutes):
        self.sent.append((staff.telegram_user_id, pending.message_id, timeout_minutes))
        return {"status": "sent", "error_message": ""}


async def test_due_pending_message_sends_one_alert(fake_redis):
    queue = RedisQueue(fake_redis)
    staff = RuleStaff(id=1, rule_id=1, telegram_user_id=9001, telegram_username="ML_YYZB3", display_name="YY_6/9_值班号3", enabled=True)
    rule = MonitorRule(id=1, chat_id="-1001", chat_name="Ops", enabled=True, staff=[staff])
    pending = PendingMessage(
        rule_id=1,
        chat_id="-1001",
        chat_name="Ops",
        message_id=50,
        message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        matched_keywords=["充值"],
        message_excerpt="充值失败",
        message_url="https://t.me/c/1001/50",
    )
    await queue.add_pending(pending, due_at=1000)
    sender = FakeAlertSender()
    worker = TimeoutWorker(queue=queue, alert_sender=sender, rules_provider=lambda: [rule], timeout_minutes=15)

    await worker.run_once(now_timestamp=1000)
    await worker.run_once(now_timestamp=1001)

    assert sender.sent == [(9001, 50, 15)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worker.py -q`

Expected: FAIL because `app.worker` does not exist.

- [ ] **Step 3: Implement alert sender and worker**

Write `app/alerts.py`:

```python
from app.models import PendingMessage, RuleStaff


def render_timeout_alert(staff: RuleStaff, pending: PendingMessage, timeout_minutes: int, private_message_status: str = "") -> str:
    username = f"@{staff.telegram_username}" if staff.telegram_username else ""
    keywords = "、".join(pending.matched_keywords)
    return "\n".join(
        [
            f"接收人员：{staff.display_name}{private_message_status} ({username})",
            f"关键词：{keywords}",
            f"群组：{pending.chat_name or pending.chat_id}",
            f"时间：{pending.message_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"状态：客户消息 {timeout_minutes} 分钟无客服回复",
            "原因：客户消息未被客服身份库中的人员引用或跟进",
            f"原消息链接：打开原消息 ({pending.message_url})",
        ]
    )


class TelegramAlertSender:
    def __init__(self, bot):
        self.bot = bot

    async def send_timeout_alert(self, staff: RuleStaff, pending: PendingMessage, timeout_minutes: int) -> dict[str, str]:
        text = render_timeout_alert(staff, pending, timeout_minutes)
        try:
            await self.bot.send_message(chat_id=staff.telegram_user_id, text=text)
            return {"status": "sent", "error_message": ""}
        except Exception as exc:
            return {"status": "failed", "error_message": str(exc)}
```

Write `app/worker.py`:

```python
from collections.abc import Callable

from app.models import MonitorRule
from app.redis_queue import RedisQueue


class TimeoutWorker:
    def __init__(
        self,
        queue: RedisQueue,
        alert_sender,
        rules_provider: Callable[[], list[MonitorRule]],
        timeout_minutes: int,
    ):
        self.queue = queue
        self.alert_sender = alert_sender
        self.rules_provider = rules_provider
        self.timeout_minutes = timeout_minutes

    async def run_once(self, now_timestamp: float) -> None:
        members = await self.queue.due_members(now_timestamp)
        rules = {rule.id: rule for rule in self.rules_provider()}
        for member in members:
            chat_id, message_id_text = member.rsplit(":", 1)
            message_id = int(message_id_text)
            pending = await self.queue.get_pending(chat_id, message_id)
            if pending is None or pending.status != "pending":
                await self.queue.remove_member(member)
                continue
            if not await self.queue.mark_alerted(chat_id, message_id):
                await self.queue.remove_member(member)
                continue
            rule = rules.get(pending.rule_id)
            if rule is None:
                await self.queue.remove_member(member)
                continue
            for staff in rule.staff:
                if staff.enabled:
                    await self.alert_sender.send_timeout_alert(staff, pending, self.timeout_minutes)
            await self.queue.remove_member(member)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_worker.py -q`

Expected: PASS.

- [ ] **Step 5: Add repository delivery record method**

Add this method to `Repository` in `app/repositories.py`:

```python
    def record_alert_delivery(
        self,
        rule_id: int,
        chat_id: str,
        message_id: int,
        matched_keyword: str,
        staff_telegram_user_id: int,
        staff_telegram_username: str,
        staff_display_name: str,
        status: str,
        error_message: str,
        sent_at: datetime | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO alert_deliveries(
                rule_id, chat_id, message_id, matched_keyword,
                staff_telegram_user_id, staff_telegram_username, staff_display_name,
                status, error_message, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                chat_id,
                message_id,
                matched_keyword,
                staff_telegram_user_id,
                staff_telegram_username,
                staff_display_name,
                status,
                error_message,
                sent_at.isoformat() if sent_at else None,
            ),
        )
        self.conn.commit()
```

- [ ] **Step 6: Run worker and repository tests**

Run: `pytest tests/test_worker.py tests/test_repositories.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

Run if `git` is available:

```bash
git add app/alerts.py app/worker.py app/repositories.py tests/test_worker.py
git commit -m "feat: send one-time timeout alerts"
```

---

### Task 7: Bot Update Handling

**Files:**
- Create: `app/bot.py`
- Create: `tests/test_bot.py`

- [ ] **Step 1: Write failing bot handler test**

Create `tests/test_bot.py`:

```python
from datetime import datetime, timezone

from app.bot import NormalizedTelegramMessage, handle_incoming_message
from app.models import MonitorRule, RuleKeyword, RuleStaff


class FakeRepo:
    def __init__(self):
        self.hits = []

    def list_enabled_rules(self):
        return [
            MonitorRule(
                id=1,
                chat_id="-1001",
                chat_name="Ops",
                enabled=True,
                keywords=[RuleKeyword(id=1, rule_id=1, keyword="充值", enabled=True, note="")],
                staff=[RuleStaff(id=1, rule_id=1, telegram_user_id=9001, telegram_username="agent", display_name="Agent", enabled=True)],
            )
        ]

    def record_keyword_hit(self, **kwargs):
        self.hits.append(kwargs)


class FakeQueue:
    def __init__(self):
        self.pending = []
        self.closed = []

    async def add_pending(self, pending, due_at):
        self.pending.append((pending, due_at))

    async def close_pending(self, chat_id, message_id):
        self.closed.append((chat_id, message_id))


async def test_keyword_message_records_hit_and_pending_task():
    repo = FakeRepo()
    queue = FakeQueue()
    message = NormalizedTelegramMessage(
        chat_id="-1001",
        chat_name="Ops",
        chat_username="",
        message_id=50,
        sender_user_id=10001,
        sender_username="customer",
        text="充值失败",
        message_time=datetime(2026, 6, 4, 13, 11, 25, tzinfo=timezone.utc),
        reply_to_message_id=None,
    )

    await handle_incoming_message(message, repo, queue, timeout_minutes=15, now_timestamp=1000)

    assert repo.hits[0]["matched_keyword"] == "充值"
    assert queue.pending[0][0].matched_keywords == ["充值"]
    assert queue.pending[0][1] == 1900
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bot.py -q`

Expected: FAIL because `app.bot` does not exist.

- [ ] **Step 3: Implement normalized handler**

Write `app/bot.py`:

```python
from dataclasses import dataclass
from datetime import datetime

from app.matcher import match_message
from app.models import PendingMessage
from app.response_detector import IncomingMessage, detect_staff_response
from app.telegram_utils import build_message_url


@dataclass(frozen=True)
class NormalizedTelegramMessage:
    chat_id: str
    chat_name: str
    chat_username: str
    message_id: int
    sender_user_id: int
    sender_username: str
    text: str
    message_time: datetime
    reply_to_message_id: int | None


async def handle_incoming_message(message: NormalizedTelegramMessage, repo, queue, timeout_minutes: int, now_timestamp: float) -> None:
    rules = repo.list_enabled_rules()
    response = detect_staff_response(
        IncomingMessage(
            chat_id=message.chat_id,
            sender_user_id=message.sender_user_id,
            message_id=message.message_id,
            reply_to_message_id=message.reply_to_message_id,
        ),
        rules,
    )
    if response is not None:
        await queue.close_pending(*response)
        return

    match = match_message(message.chat_id, message.text, rules)
    if match is None:
        return

    url = build_message_url(message.chat_id, message.message_id, message.chat_username)
    for keyword in match.matched_keywords:
        repo.record_keyword_hit(
            rule_id=match.rule.id,
            chat_id=message.chat_id,
            chat_name=message.chat_name,
            message_id=message.message_id,
            telegram_user_id=message.sender_user_id,
            telegram_username=message.sender_username,
            matched_keyword=keyword,
            message_excerpt=message.text[:200],
            message_url=url,
            message_time=message.message_time,
        )
    await queue.add_pending(
        PendingMessage(
            rule_id=match.rule.id,
            chat_id=message.chat_id,
            chat_name=message.chat_name,
            message_id=message.message_id,
            message_time=message.message_time,
            matched_keywords=match.matched_keywords,
            message_excerpt=message.text[:200],
            message_url=url,
        ),
        due_at=now_timestamp + timeout_minutes * 60,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bot.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run if `git` is available:

```bash
git add app/bot.py tests/test_bot.py
git commit -m "feat: handle telegram monitored messages"
```

---

### Task 8: FastAPI App and Webhook

**Files:**
- Create: `tests/test_admin_routes.py`
- Create: `app/main.py`

- [ ] **Step 1: Write failing route smoke tests**

Create `tests/test_admin_routes.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_admin_stats_page_loads():
    client = TestClient(create_app())
    response = client.get("/admin")

    assert response.status_code == 200
    assert "关键词命中" in response.text


def test_telegram_webhook_accepts_empty_payload():
    client = TestClient(create_app())
    response = client.post("/webhook/telegram", json={})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_admin_routes.py -q`

Expected: FAIL because `app.main` does not exist.

- [ ] **Step 3: Implement FastAPI app shell**

Write `app/main.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


def create_app() -> FastAPI:
    app = FastAPI(title="Telegram Alert Bot")
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_stats():
        return """
        <!doctype html>
        <html lang="zh-CN">
        <head><meta charset="utf-8"><title>统计总览</title></head>
        <body><main><h1>关键词命中</h1></main></body>
        </html>
        """

    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request):
        await request.json()
        return {"ok": True}

    return app


app = create_app()
```

- [ ] **Step 4: Create static directory**

Create directory `app/static`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_admin_routes.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run if `git` is available:

```bash
git add app/main.py tests/test_admin_routes.py
git commit -m "feat: add fastapi app shell"
```

---

### Task 9: Web Admin UI

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/admin_stats.html`
- Create: `app/templates/admin_rules.html`
- Create: `app/templates/admin_alerts.html`
- Create: `app/static/styles.css`
- Create: `app/static/admin.js`
- Modify: `app/main.py`
- Modify: `tests/test_admin_routes.py`

- [ ] **Step 1: Extend failing route tests**

Add to `tests/test_admin_routes.py`:

```python
def test_admin_rules_page_loads():
    client = TestClient(create_app())
    response = client.get("/admin/rules")

    assert response.status_code == 200
    assert "监控规则配置" in response.text
    assert "批量导入关键词" in response.text


def test_admin_alerts_page_loads():
    client = TestClient(create_app())
    response = client.get("/admin/alerts")

    assert response.status_code == 200
    assert "预警记录" in response.text
    assert "发送状态" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_admin_routes.py -q`

Expected: FAIL because `/admin/rules` and `/admin/alerts` are missing.

- [ ] **Step 3: Create web CSS**

Write `app/static/styles.css` with these design tokens and layout primitives:

```css
:root {
  --bg: #020617;
  --panel: #0f172a;
  --panel-2: #1e293b;
  --text: #f8fafc;
  --muted: #94a3b8;
  --border: #334155;
  --success: #22c55e;
  --warning: #f59e0b;
  --danger: #ef4444;
  --radius: 8px;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Fira Sans", "Microsoft YaHei", system-ui, sans-serif;
}
a { color: inherit; }
.app-shell { display: grid; grid-template-columns: 240px 1fr; min-height: 100dvh; }
.sidebar { border-right: 1px solid var(--border); padding: 20px; background: #050b18; }
.brand { font-weight: 700; margin-bottom: 24px; }
.nav-link { display: block; padding: 10px 12px; border-radius: var(--radius); color: var(--muted); text-decoration: none; }
.nav-link.active, .nav-link:hover { background: var(--panel-2); color: var(--text); }
.main { padding: 24px; max-width: 1400px; width: 100%; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; }
.metric-value { font-family: "Fira Code", Consolas, monospace; font-size: 28px; font-weight: 700; }
.muted { color: var(--muted); }
.rule-row { display: grid; grid-template-columns: 1.3fr 1.4fr 1.2fr auto; gap: 12px; align-items: center; }
.chip { display: inline-flex; align-items: center; min-height: 28px; padding: 4px 8px; border: 1px solid var(--border); border-radius: 999px; margin: 2px; color: var(--text); }
.chip.off { color: var(--muted); opacity: 0.7; }
.button { min-height: 40px; border: 1px solid var(--border); border-radius: 6px; background: var(--panel-2); color: var(--text); padding: 0 12px; cursor: pointer; }
.button.primary { background: var(--success); border-color: var(--success); color: #02110a; font-weight: 700; }
.button:disabled { opacity: .5; cursor: not-allowed; }
.status-danger { color: var(--danger); }
.status-warning { color: var(--warning); }
.status-success { color: var(--success); }
@media (max-width: 860px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { position: sticky; top: 0; z-index: 10; display: flex; gap: 8px; overflow-x: auto; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .rule-row { grid-template-columns: 1fr; }
}
```

- [ ] **Step 4: Create admin JS**

Write `app/static/admin.js`:

```javascript
function previewKeywordImport(text) {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const seen = new Set();
  let duplicate = 0;
  const fresh = [];
  for (const line of lines) {
    if (seen.has(line)) {
      duplicate += 1;
    } else {
      seen.add(line);
      fresh.push(line);
    }
  }
  return { total: lines.length, fresh, duplicate };
}

window.previewKeywordImport = previewKeywordImport;
```

- [ ] **Step 5: Create admin templates**

Write `app/templates/base.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <div class="app-shell">
    <nav class="sidebar" aria-label="主导航">
      <div class="brand">Telegram Alert Bot</div>
      <a class="nav-link" href="/admin">统计总览</a>
      <a class="nav-link" href="/admin/rules">监控规则配置</a>
      <a class="nav-link" href="/admin/alerts">预警记录</a>
    </nav>
    <main class="main">
      {% block content %}{% endblock %}
    </main>
  </div>
  <script src="/static/admin.js"></script>
</body>
</html>
```

Write `app/templates/admin_stats.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>统计总览</h1>
<section class="metric-grid" aria-label="核心指标">
  <article class="card"><div class="muted">今日关键词命中</div><div class="metric-value">0</div></article>
  <article class="card"><div class="muted">监控群数量</div><div class="metric-value">0</div></article>
  <article class="card"><div class="muted">待响应消息</div><div class="metric-value">0</div></article>
  <article class="card"><div class="muted">今日超时提醒</div><div class="metric-value">0</div></article>
</section>
<section class="card" style="margin-top:16px"><h2>关键词命中趋势</h2><p class="muted">暂无数据</p></section>
{% endblock %}
```

Write `app/templates/admin_rules.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>监控规则配置</h1>
<section class="card">
  <div class="rule-row">
    <div><strong>Ops Group</strong><div class="muted">chat id: -1001571955528</div></div>
    <div><span class="chip">充值</span><span class="chip">失败</span></div>
    <div><span class="chip">YY_6/9_值班号3</span></div>
    <button class="button">编辑</button>
  </div>
</section>
<section class="card" style="margin-top:16px">
  <h2>批量导入关键词</h2>
  <textarea aria-label="批量导入关键词" rows="6" style="width:100%;background:var(--panel-2);color:var(--text);border:1px solid var(--border);border-radius:6px"></textarea>
  <button class="button primary" style="margin-top:12px">解析预览</button>
</section>
{% endblock %}
```

Write `app/templates/admin_alerts.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>预警记录</h1>
<section class="card">
  <table style="width:100%;border-collapse:collapse">
    <thead><tr><th align="left">时间</th><th align="left">群组</th><th align="left">关键词</th><th align="left">发送状态</th></tr></thead>
    <tbody><tr><td colspan="4" class="muted">暂无预警记录</td></tr></tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 6: Wire templates in FastAPI**

Replace page handlers in `app/main.py` with Jinja templates:

```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def create_app() -> FastAPI:
    app = FastAPI(title="Telegram Alert Bot")
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_stats(request: Request):
        return templates.TemplateResponse("admin_stats.html", {"request": request, "title": "统计总览"})

    @app.get("/admin/rules", response_class=HTMLResponse)
    async def admin_rules(request: Request):
        return templates.TemplateResponse("admin_rules.html", {"request": request, "title": "监控规则配置"})

    @app.get("/admin/alerts", response_class=HTMLResponse)
    async def admin_alerts(request: Request):
        return templates.TemplateResponse("admin_alerts.html", {"request": request, "title": "预警记录"})

    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request):
        await request.json()
        return {"ok": True}

    return app


app = create_app()
```

- [ ] **Step 7: Run admin route tests**

Run: `pytest tests/test_admin_routes.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

Run if `git` is available:

```bash
git add app/templates app/static app/main.py tests/test_admin_routes.py
git commit -m "feat: add web admin console"
```

---

### Task 10: Telegram Mini App UI

**Files:**
- Create: `tests/test_miniapp_routes.py`
- Create: `app/templates/mini_today.html`
- Create: `app/templates/mini_rules.html`
- Create: `app/templates/mini_me.html`
- Create: `app/static/miniapp.js`
- Modify: `app/main.py`
- Modify: `app/static/styles.css`

- [ ] **Step 1: Write failing Mini App route tests**

Create `tests/test_miniapp_routes.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_mini_today_page_loads():
    client = TestClient(create_app())
    response = client.get("/mini")

    assert response.status_code == 200
    assert "今日" in response.text
    assert "打开原消息" in response.text


def test_mini_rules_page_loads():
    client = TestClient(create_app())
    response = client.get("/mini/rules")

    assert response.status_code == 200
    assert "我的规则" in response.text


def test_mini_me_page_loads():
    client = TestClient(create_app())
    response = client.get("/mini/me")

    assert response.status_code == 200
    assert "我的" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_miniapp_routes.py -q`

Expected: FAIL because Mini App routes do not exist.

- [ ] **Step 3: Add Mini App CSS**

Append to `app/static/styles.css`:

```css
.mini-body { max-width: 560px; margin: 0 auto; padding: 16px 16px 88px; }
.mini-tabs {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
  background: rgba(2, 6, 23, .96);
  border-top: 1px solid var(--border);
}
.mini-tab {
  min-height: 44px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  text-decoration: none;
  color: var(--muted);
}
.mini-tab.active { background: var(--panel-2); color: var(--text); }
.alert-row { display: grid; gap: 8px; }
```

- [ ] **Step 4: Create Mini App JS**

Write `app/static/miniapp.js`:

```javascript
if (window.Telegram && window.Telegram.WebApp) {
  window.Telegram.WebApp.ready();
  window.Telegram.WebApp.expand();
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
}

window.copyText = copyText;
```

- [ ] **Step 5: Create Mini App templates**

Write `app/templates/mini_today.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>今日</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <main class="mini-body">
    <h1>今日</h1>
    <section class="card"><div class="muted">我负责的关键词命中</div><div class="metric-value">0</div></section>
    <section class="card" style="margin-top:12px">
      <h2>最近超时提醒</h2>
      <div class="alert-row">
        <span class="muted">暂无提醒</span>
        <button class="button primary">打开原消息</button>
      </div>
    </section>
  </main>
  <nav class="mini-tabs" aria-label="Mini App 导航">
    <a class="mini-tab active" href="/mini">今日</a>
    <a class="mini-tab" href="/mini/rules">规则</a>
    <a class="mini-tab" href="/mini/me">我的</a>
  </nav>
  <script src="/static/miniapp.js"></script>
</body>
</html>
```

Write `app/templates/mini_rules.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>我的规则</title><link rel="stylesheet" href="/static/styles.css"></head>
<body>
  <main class="mini-body"><h1>我的规则</h1><section class="card"><p class="muted">暂无分配规则</p></section></main>
  <nav class="mini-tabs" aria-label="Mini App 导航"><a class="mini-tab" href="/mini">今日</a><a class="mini-tab active" href="/mini/rules">规则</a><a class="mini-tab" href="/mini/me">我的</a></nav>
  <script src="/static/miniapp.js"></script>
</body>
</html>
```

Write `app/templates/mini_me.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>我的</title><link rel="stylesheet" href="/static/styles.css"></head>
<body>
  <main class="mini-body"><h1>我的</h1><section class="card"><p class="muted">等待 Telegram 身份信息</p></section></main>
  <nav class="mini-tabs" aria-label="Mini App 导航"><a class="mini-tab" href="/mini">今日</a><a class="mini-tab" href="/mini/rules">规则</a><a class="mini-tab active" href="/mini/me">我的</a></nav>
  <script src="/static/miniapp.js"></script>
</body>
</html>
```

- [ ] **Step 6: Add Mini App routes**

Add to `create_app()` in `app/main.py`:

```python
    @app.get("/mini", response_class=HTMLResponse)
    async def mini_today(request: Request):
        return templates.TemplateResponse("mini_today.html", {"request": request, "title": "今日"})

    @app.get("/mini/rules", response_class=HTMLResponse)
    async def mini_rules(request: Request):
        return templates.TemplateResponse("mini_rules.html", {"request": request, "title": "我的规则"})

    @app.get("/mini/me", response_class=HTMLResponse)
    async def mini_me(request: Request):
        return templates.TemplateResponse("mini_me.html", {"request": request, "title": "我的"})
```

- [ ] **Step 7: Run Mini App tests**

Run: `pytest tests/test_miniapp_routes.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

Run if `git` is available:

```bash
git add app/templates/mini_today.html app/templates/mini_rules.html app/templates/mini_me.html app/static/styles.css app/static/miniapp.js app/main.py tests/test_miniapp_routes.py
git commit -m "feat: add telegram mini app views"
```

---

### Task 11: Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run complete test suite**

Run:

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run local server**

Run:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected: server starts and exposes:

- `http://127.0.0.1:8000/admin`
- `http://127.0.0.1:8000/admin/rules`
- `http://127.0.0.1:8000/admin/alerts`
- `http://127.0.0.1:8000/mini`

- [ ] **Step 3: Verify UI manually**

Open the pages above and verify:

- no horizontal scroll at 375px viewport width
- admin navigation is visible
- Mini App bottom navigation does not cover content
- primary actions are at least 44px high
- dark theme text is readable

- [ ] **Step 4: Update README routes**

Add this section to `README.md`:

```markdown
## Pages

- Web admin: `/admin`
- Monitoring rules: `/admin/rules`
- Alert deliveries: `/admin/alerts`
- Telegram Mini App: `/mini`
```

- [ ] **Step 5: Commit**

Run if `git` is available:

```bash
git add README.md
git commit -m "docs: document admin and mini app routes"
```
