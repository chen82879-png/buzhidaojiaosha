# V22 Alert Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the stable v22 Telegram alert bot with independent keyword statistics/task/alert switches, a one-time severe alert 10 minutes after the first timeout, unified deleted-message cancellation, and completed-task acknowledgement suppression.

**Architecture:** Keep SQLite as the task/configuration source of truth and Redis as a recoverable scheduling cache. Add explicit model fields and repository queries, then keep message classification, timeout delivery, deletion polling, and the mini keyword UI as separate tested boundaries.

**Tech Stack:** Python 3.12+, FastAPI, SQLite, redis-py asyncio, Telethon, Jinja2, pytest, pytest-asyncio.

---

## File Map

- `app/db.py`: additive SQLite migrations for keyword layers and severe-alert timestamps.
- `app/models.py`: typed configuration and task fields.
- `app/repositories.py`: persistence, due severe-task queries, and context-based deletion cancellation.
- `app/matcher.py`: separate fixed-keyword recognition from task/alert eligibility.
- `app/ignore_words.py`: completed acknowledgement normalization and exact matching.
- `app/bot.py`: layered keyword behavior and customer acknowledgement suppression.
- `app/redis_queue.py`: normal and severe queue keys and cleanup.
- `app/alerts.py`: severe alert rendering/sending.
- `app/worker.py`: normal alert scheduling followed by idempotent severe delivery.
- `app/poller.py`: unified deletion cancellation for all context-linked task types.
- `app/main.py`, `app/templates/mini_keywords.html`, `app/static/styles.css`: three-switch configuration UI and task severe-state labels.
- `tests/`: focused TDD coverage for every behavior.

### Task 1: Add Backward-Compatible Data Fields

**Files:**
- Modify: `app/db.py`
- Modify: `app/models.py`
- Modify: `app/repositories.py`
- Test: `tests/test_repositories.py`

- [ ] **Step 1: Write failing migration and round-trip tests**

Add tests proving an old v22 database gains the new columns and preserves old behavior:

```python
def test_migrate_adds_keyword_layers_and_severe_alert_fields(tmp_path):
    conn = connect(str(tmp_path / "app.sqlite3"))
    migrate(conn)
    keyword_columns = {row["name"] for row in conn.execute("PRAGMA table_info(keyword_configs)")}
    task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(monitor_tasks)")}
    assert {"stats_enabled", "task_enabled", "alert_enabled"} <= keyword_columns
    assert {"first_alert_sent_at", "severe_due_at", "severe_alert_sent_at"} <= task_columns


def test_existing_enabled_keyword_defaults_all_layers_on(tmp_path):
    repo = build_repo(tmp_path)
    repo.save_keyword_configs([
        KeywordConfig(keyword="请稍等elk", enabled=True, recipient_chat_ids=[10001])
    ])
    config = next(item for item in repo.list_keyword_configs() if item.keyword == "请稍等elk")
    assert config.stats_enabled is True
    assert config.task_enabled is True
    assert config.alert_enabled is True
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
& 'D:\ptyhon\python.exe' -m pytest tests\test_repositories.py -q -p no:cacheprovider --basetemp C:\Users\rog\Documents\grybuges\.tmp\pytest-v22-data-red
```

Expected: FAIL because the columns and dataclass fields do not exist.

- [ ] **Step 3: Add additive migrations and model fields**

Extend `KeywordConfig` while preserving `enabled` as a compatibility alias during the migration:

```python
@dataclass(frozen=True)
class KeywordConfig:
    keyword: str
    enabled: bool
    recipient_chat_ids: list[int]
    alert_enabled: bool = True
    stats_enabled: bool = True
    task_enabled: bool = True
```

Extend `MonitorTask` with nullable timestamps:

```python
first_alert_sent_at: datetime | None = None
severe_due_at: datetime | None = None
severe_alert_sent_at: datetime | None = None
```

In `migrate()`, add missing columns with `ALTER TABLE`. Existing `enabled=1` rows migrate to all three layers enabled; existing `enabled=0` rows keep statistics/task disabled and cannot alert.

- [ ] **Step 4: Update repository reads/writes and task conversion**

Normalize invalid combinations before persistence:

```python
task_enabled = bool(config.task_enabled)
alert_enabled = bool(config.alert_enabled and task_enabled)
```

Parse nullable task timestamps with `datetime.fromisoformat()` only when values are present.

- [ ] **Step 5: Run repository tests and commit**

Expected: all repository tests PASS.

```powershell
git add app/db.py app/models.py app/repositories.py tests/test_repositories.py
git commit -m "feat: add layered keyword and severe alert state"
```

### Task 2: Implement Layered Keyword Behavior and Acknowledgement Suppression

**Files:**
- Modify: `app/matcher.py`
- Modify: `app/ignore_words.py`
- Modify: `app/bot.py`
- Test: `tests/test_matcher.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write failing layered-behavior tests**

Add four independent tests using the existing `FakeRepo`, `FakeQueue`, and `NormalizedTelegramMessage` fixtures:

- `test_stats_only_keyword_records_hit_without_task`: configure `stats_enabled=True`, `task_enabled=False`, `alert_enabled=False`; assert one hit, no task, and no queue member.
- `test_task_enabled_alert_disabled_creates_task_without_recipient_alert_route`: configure statistics and task on with alerts off; assert one hit, one wait task with empty recipients, and one pending queue entry.
- `test_all_layers_disabled_does_nothing`: configure all layers off; assert no hit, task, or queue entry.
- `test_alert_enabled_implies_task_enabled_after_config_normalization`: save an invalid `task_enabled=False`, `alert_enabled=True` config and assert the repository reads it back with both task and alert enabled.

The task-without-alert case creates the SQLite task but does not add a Telegram delivery recipient. It may still be queued so the task transitions to timed-out state without sending.

- [ ] **Step 2: Write failing completed-acknowledgement tests**

Use the exact acknowledgement set `1`, `好的`, `明白`, `谢谢`, `ok`, `知道了` and add these tests:

- `test_completed_task_customer_ack_reply_does_not_create_any_task`: create and complete a wait task, then send `1` replying to either the root or staff answer; assert the task remains completed and the task count does not increase.
- `test_completed_task_unreferenced_customer_ack_does_not_create_any_task`: after completion send unreferenced `好的`; assert no reply/follow-up/self-reply task and no queue entry.
- `test_account_number_containing_one_is_not_acknowledgement`: send `查询12345`; assert it follows normal reply-task behavior.
- `test_word_containing_ok_is_not_acknowledgement`: send `token异常`; assert it follows normal reply-task behavior.

- [ ] **Step 3: Run focused tests and verify RED**

```powershell
& 'D:\ptyhon\python.exe' -m pytest tests\test_matcher.py tests\test_bot.py -q -p no:cacheprovider --basetemp C:\Users\rog\Documents\grybuges\.tmp\pytest-v22-layered-red
```

Expected: FAIL on missing layered behavior and unreferenced acknowledgement suppression.

- [ ] **Step 4: Implement exact acknowledgement matching**

In `app/ignore_words.py` add:

```python
COMPLETED_ACK_WORDS = {"1", "好的", "明白", "谢谢", "ok", "知道了"}

def is_completed_acknowledgement(text: str) -> bool:
    return normalize_ignore_text(text) in {
        normalize_ignore_text(word) for word in COMPLETED_ACK_WORDS
    }
```

Do not use substring matching.

- [ ] **Step 5: Implement the three message paths**

In `handle_incoming_message()`:

1. Record fixed-keyword hits only when `stats_enabled`.
2. Create wait tasks only when `task_enabled`.
3. Store alert recipients only when `alert_enabled`.
4. Suppress a customer acknowledgement before follow-up/reply/self-reply creation.
5. For unreferenced acknowledgements, suppress only that message; do not complete or mutate unrelated open tasks.

- [ ] **Step 6: Run focused tests and commit**

```powershell
git add app/matcher.py app/ignore_words.py app/bot.py tests/test_matcher.py tests/test_bot.py
git commit -m "feat: separate keyword layers and suppress acknowledgements"
```

### Task 3: Add One-Time Severe Timeout Alerts

**Files:**
- Modify: `app/redis_queue.py`
- Modify: `app/repositories.py`
- Modify: `app/alerts.py`
- Modify: `app/worker.py`
- Test: `tests/test_redis_queue.py`
- Test: `tests/test_repositories.py`
- Test: `tests/test_alerts.py`
- Test: `tests/test_worker.py`

- [ ] **Step 1: Write failing queue and repository tests**

Required tests and exact assertions:

- `test_add_and_close_severe_queue_member`: add task 20 to `severe_timeout_queue` at 1600, assert it is due at 1600, call `close_pending(20)`, then assert neither normal nor severe queue returns task 20.
- `test_mark_first_alert_sets_severe_due_ten_minutes_later`: mark first alert at `2026-06-19T10:00:00Z`, assert `first_alert_sent_at` matches and `severe_due_at` is `10:10:00Z`.
- `test_list_due_severe_tasks_returns_only_open_unsent_tasks`: create pending, completed, deleted, and already-severe-sent rows with the same due time; assert only the pending unsent task is returned.
- `test_mark_severe_alerted_is_idempotent`: mark task 20 severe-alerted twice and assert the persisted timestamp remains the first timestamp.

- [ ] **Step 2: Write failing worker tests**

- `test_first_alert_schedules_severe_alert_ten_minutes_later`: run a due normal task at timestamp 1000 and assert first-alert state plus a severe queue score of 1600.
- `test_due_severe_alert_sends_once`: run at 1600 and 1601; assert one severe send and one persisted severe timestamp.
- `test_completed_task_never_sends_severe_alert`: complete before 1600 and assert zero severe sends plus queue cleanup.
- `test_deleted_task_never_sends_severe_alert`: delete before 1600 and assert zero severe sends plus queue cleanup.
- `test_worker_recovers_due_severe_alert_from_sqlite_without_redis`: omit the Redis severe member, return the task from `list_due_severe_tasks()`, and assert one severe send.

- [ ] **Step 3: Run focused tests and verify RED**

```powershell
& 'D:\ptyhon\python.exe' -m pytest tests\test_redis_queue.py tests\test_repositories.py tests\test_alerts.py tests\test_worker.py -q -p no:cacheprovider --basetemp C:\Users\rog\Documents\grybuges\.tmp\pytest-v22-severe-red
```

- [ ] **Step 4: Add severe queue primitives**

Use distinct keys:

```python
@staticmethod
def severe_member(task_id: int) -> str:
    return str(task_id)

async def add_severe(self, task_id: int, due_at: float) -> None:
    await self.redis.zadd("severe_timeout_queue", {self.severe_member(task_id): due_at})
```

`close_pending(task_id)` must remove pending data, normal queue, normal idempotency key, severe queue, and severe idempotency key.

- [ ] **Step 5: Add repository state transitions**

Implement:

```python
mark_first_alert_sent(task_id, sent_at, severe_due_at)
list_due_severe_tasks(now)
mark_severe_alert_sent(task_id, sent_at)
```

`list_due_severe_tasks()` requires an open status, non-null first alert, due time reached, and null severe sent time.

- [ ] **Step 6: Render and send severe alerts**

Add `render_severe_timeout_alert()` and `send_severe_timeout_alert()` using the existing task recipients and link. The title/status must clearly say the first alert was sent 10 minutes earlier and the task remains unresolved.

- [ ] **Step 7: Extend worker flow**

After successful normal delivery, persist first-alert state and schedule severe due time. On every pass, merge Redis and SQLite severe due tasks, re-read task status immediately before sending, then persist the severe sent timestamp once.

- [ ] **Step 8: Run focused tests and commit**

```powershell
git add app/redis_queue.py app/repositories.py app/alerts.py app/worker.py tests/test_redis_queue.py tests/test_repositories.py tests/test_alerts.py tests/test_worker.py
git commit -m "feat: add idempotent severe timeout alerts"
```

### Task 4: Unify Deleted-Message Cancellation

**Files:**
- Modify: `app/repositories.py`
- Modify: `app/poller.py`
- Modify: `app/listener.py`
- Test: `tests/test_repositories.py`
- Test: `tests/test_poller.py`

- [ ] **Step 1: Write failing context-deletion tests**

Create one open task of each type and attach an additional context message.

- `test_delete_tasks_referencing_cancels_all_four_task_types`: delete one linked message for each wait, follow-up, reply, and self-reply task; assert all four returned task IDs are marked `deleted`.
- `test_delete_tasks_referencing_is_idempotent`: call deletion twice for the same message; assert the first call returns the task and the second returns an empty list.

- [ ] **Step 2: Write failing poller tests**

- `test_deleted_context_message_closes_normal_and_severe_queue`: seed both queue types for one task, report an attached context message deleted, and assert both queues are empty.
- `test_deleted_wait_promotes_valid_duplicate_after_cleanup`: delete the active wait message, retain a valid duplicate, and assert the duplicate becomes pending with one normal queue entry.
- `test_deleted_task_is_excluded_from_stats_and_history`: mark the linked wait deleted and assert keyword totals, closure totals, and anomaly totals exclude it.

- [ ] **Step 3: Run tests and verify RED**

```powershell
& 'D:\ptyhon\python.exe' -m pytest tests\test_repositories.py tests\test_poller.py -q -p no:cacheprovider --basetemp C:\Users\rog\Documents\grybuges\.tmp\pytest-v22-delete-red
```

- [ ] **Step 4: Implement repository cancellation by context**

Add one method that joins `monitor_task_context_messages` and matches root/wait/trigger IDs. Only open states are changed:

```python
def delete_open_tasks_referencing(self, chat_id: str, message_id: int) -> list[MonitorTask]:
    rows = self.conn.execute(
        "SELECT DISTINCT mt.* FROM monitor_tasks mt "
        "LEFT JOIN monitor_task_context_messages ctx ON ctx.task_id = mt.id "
        "WHERE mt.chat_id = ? AND mt.status IN ('pending', 'alerted') "
        "AND (? IN (mt.root_message_id, mt.wait_message_id, mt.trigger_message_id) "
        "OR ctx.message_id = ?) ORDER BY mt.id",
        (chat_id, message_id, message_id),
    ).fetchall()
    self.conn.executemany(
        "UPDATE monitor_tasks SET status = 'deleted' WHERE id = ?",
        [(row["id"],) for row in rows],
    )
    self.conn.commit()
    return [self._task_from_row(row) for row in rows]
```

Mark matching tasks `deleted` in one transaction and return their pre-update task data for queue cleanup.

- [ ] **Step 5: Route all deletion handling through the new method**

The poller checks every distinct context message associated with open tasks, calls the repository cancellation method, and invokes `queue.close_pending()` for each result. Keep v22 duplicate-wait promotion after a deleted active wait.

- [ ] **Step 6: Run focused tests and commit**

```powershell
git add app/repositories.py app/poller.py app/listener.py tests/test_repositories.py tests/test_poller.py
git commit -m "feat: cancel all task types on linked message deletion"
```

### Task 5: Update Keyword UI and Verify End to End

**Files:**
- Modify: `app/main.py`
- Modify: `app/templates/mini_keywords.html`
- Modify: `app/static/styles.css`
- Modify: `app/templates/mini_tasks.html`
- Test: `tests/test_miniapp_routes.py`
- Test: `tests/test_worker_loop.py`

- [ ] **Step 1: Write failing route/UI tests**

Verify the keyword form renders and saves all switches and normalizes dependencies:

- `test_keyword_page_renders_statistics_task_and_alert_switches`: GET `/mini/keywords`; assert the HTML contains `stats_enabled::请稍等elk`, `task_enabled::请稍等elk`, and `alert_enabled::请稍等elk`.
- `test_keyword_post_disabling_task_also_disables_alert`: POST statistics and alert without task; assert the saved configuration has task and alert both false.
- `test_keyword_post_enabling_alert_enables_task`: POST alert with an omitted task checkbox; assert the saved configuration has task and alert both true.
- `test_task_page_shows_severe_alert_state`: return a pending task with first-alert and severe-due timestamps; assert `/mini/tasks` contains the severe due label.

- [ ] **Step 2: Run route tests and verify RED**

```powershell
& 'D:\ptyhon\python.exe' -m pytest tests\test_miniapp_routes.py -q -p no:cacheprovider --basetemp C:\Users\rog\Documents\grybuges\.tmp\pytest-v22-ui-red
```

- [ ] **Step 3: Implement compact three-switch UI**

Render `统计`, `任务`, and `超时预警` toggles for each keyword. Keep the existing white mobile layout and recipient input. Add small browser-side dependency handling, but repeat the same normalization in the POST route.

- [ ] **Step 4: Add severe state to task views**

`build_task_view()` exposes `first_alert_sent_at`, `severe_due_at`, and `severe_alert_sent_at` labels. The task template shows a compact status line without adding a page or changing navigation.

- [ ] **Step 5: Run all tests**

```powershell
& 'D:\ptyhon\python.exe' -m pytest -q -p no:cacheprovider --basetemp C:\Users\rog\Documents\grybuges\.tmp\pytest-v22-alert-enhancements-full
```

Expected: all tests PASS with no failures.

- [ ] **Step 6: Run static and import checks**

```powershell
& 'D:\ptyhon\python.exe' -m compileall -q app
& 'D:\ptyhon\python.exe' -c "from app.main import app; print(app.title)"
git diff --check
```

Expected: compile succeeds, title is `Telegram Alert Bot`, and `git diff --check` reports nothing.

- [ ] **Step 7: Commit the UI and integration work**

```powershell
git add app/main.py app/templates/mini_keywords.html app/templates/mini_tasks.html app/static/styles.css tests/test_miniapp_routes.py tests/test_worker_loop.py
git commit -m "feat: expose layered alert controls"
```

- [ ] **Step 8: Pre-deployment verification**

Compare the branch to `b04cb6e`, confirm no monitoring group, bot token, listener session, or recipient Chat ID constants changed, then package the branch for a Zeabur preview/deployment. Do not deploy until the full suite and online rollback package are both available.
