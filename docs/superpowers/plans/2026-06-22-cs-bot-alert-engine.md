# CS Bot Alert Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current alert behavior with the real-time and AI alert rules from `mingf848-hue/cs-bot@a1da1e8`, excluding replies, integrations, extensions, and business automation.

**Architecture:** Keep FastAPI, Telethon, SQLite, Redis configuration, and the four-page miniapp. Isolate staff recognition and AI analysis in focused modules, use the existing task records only as runtime projections, clear active projections and queues at startup, and implement the source state transitions in the Telegram handler.

**Tech Stack:** Python 3, FastAPI, Telethon, aiogram, SQLite, Redis, Gemini REST API, pytest

---

### Task 1: Staff identity and source configuration

**Files:**
- Create: `app/staff_identity.py`
- Modify: `app/config.py`
- Modify: `app/listener.py`
- Modify: `app/main.py`
- Modify: `.env.example`
- Create: `tests/test_staff_identity.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_listener.py`

- [ ] Write failing tests for recognition by listener ID, 13 explicit IDs, exact names, and `YY_6/9_值班号`/`Y_YY` prefixes.
- [ ] Verify tests fail because no centralized staff recognizer or settings exist.
- [ ] Add settings for `OTHER_CS_IDS`, explicit staff names, `KEEP_KEYWORDS`, `IGNORE_KEYWORDS`, `GEMINI_API_KEY`, and `GEMINI_MODEL`.
- [ ] Extend normalized Telegram messages with display name, media group ID, and message kind.
- [ ] Use one `StaffIdentity` object in webhook and Telethon paths.
- [ ] Run staff, config, listener, and webhook tests.
- [ ] Commit as `feat: add cs-bot staff identity rules`.

### Task 2: Source-compatible real-time state machine

**Files:**
- Create: `app/alert_rules.py`
- Modify: `app/bot.py`
- Modify: `app/worker.py`
- Modify: `app/repositories.py`
- Modify: `app/redis_queue.py`
- Modify: `app/main.py`
- Modify: `app/poller.py`
- Modify: `tests/test_bot.py`
- Modify: `tests/test_worker.py`
- Modify: `tests/test_repositories.py`
- Modify: `tests/test_redis_queue.py`
- Modify: `tests/test_poller.py`

- [ ] Write failing tests for exact timeouts: wait 12 minutes, severe wait at 22 minutes, follow-up 15 minutes, missed reply five minutes, and self-reply three minutes.
- [ ] Write failing tests for staff wait triggers requiring a customer reference and an alert-enabled wait keyword.
- [ ] Write failing tests for wait reset, wait-to-follow-up, follow-up reset, follow-up-to-wait, and normal-result completion.
- [ ] Write failing tests for missed reply only when a customer references staff in a flow with selected wait history; reject unreferenced global messages.
- [ ] Write failing tests for customer self-reply, exact ignore words, media-album deduplication, latest-task replacement, and independent flows.
- [ ] Write failing tests that every related deletion cancels the active task and suppresses severe alerts.
- [ ] Add source constants and exact normalized ignore/follow-up matching in `alert_rules.py`.
- [ ] Add repository lookups for selected wait history and related-flow context.
- [ ] Refactor `handle_incoming_message` into explicit staff/customer branches matching source transition order.
- [ ] Clear active task rows and Redis timeout members during application startup so restart does not restore countdowns.
- [ ] Keep completed/deleted records for history while treating only the current process generation as active.
- [ ] Run all real-time rule tests and commit as `feat: implement cs-bot alert state machine`.

### Task 3: Work mode and source failure behavior

**Files:**
- Create: `app/work_mode.py`
- Modify: `app/listener.py`
- Modify: `app/main.py`
- Modify: `app/alerts.py`
- Create: `tests/test_work_mode.py`
- Modify: `tests/test_listener.py`
- Modify: `tests/test_alerts.py`

- [ ] Write failing tests for `上班`, `下班`, and `状态` commands.
- [ ] Write failing tests that off-duty mode records snapshots, creates no tasks, and clears active countdowns.
- [ ] Write failing tests that returning to work does not reconstruct off-duty tasks.
- [ ] Implement an in-process work-mode controller and saved-message command handling.
- [ ] Preserve source delivery failure behavior: log once and do not retry bot messages.
- [ ] Run focused tests and commit as `feat: add cs-bot work mode`.

### Task 4: Gemini alert analysis and historical audit

**Files:**
- Create: `app/ai_audit.py`
- Modify: `app/repositories.py`
- Modify: `app/main.py`
- Modify: `app/templates/mini_history.html`
- Create: `tests/test_ai_audit.py`
- Modify: `tests/test_repositories.py`
- Modify: `tests/test_miniapp_routes.py`

- [ ] Write failing tests for reply-needed, orphan-context, and continuation prompts and JSON parsing.
- [ ] Write failing tests for conservative failures: needs review, not exempt, and new question.
- [ ] Write failing tests for explicit-reference closure, sticker/GIF exclusion, whitelist approval, leader approval, and `同意后处理` behavior.
- [ ] Write failing tests for 10-hour off-duty, 12-hour ordinary, and 20-hour full lookback windows, including the two source excluded groups.
- [ ] Implement a timeout-bounded Gemini REST client with source-compatible prompts and defaults.
- [ ] Add read-only snapshot queries and pure audit classification functions.
- [ ] Expose keyword/full audit actions and results through the existing History page; add no new page.
- [ ] Trigger the 10-hour audit before off-duty runtime cleanup.
- [ ] Run AI, repository, and miniapp tests and commit as `feat: add cs-bot ai alert audits`.

### Task 5: Full verification and Zeabur deployment

**Files:**
- Modify only if verification reveals a tested defect.

- [ ] Run `D:\ptyhon\python.exe -m pytest -q -p no:cacheprovider` in a fresh temporary directory.
- [ ] Run `D:\ptyhon\python.exe -m compileall -q app` and import `app.main`.
- [ ] Confirm no Zendesk, private AI reply, Chrome extension, or business automation code was added.
- [ ] Confirm the 13 explicit staff IDs, 11 group names, 18 keywords, bot token variables, session path, and domain configuration remain intact.
- [ ] Package only committed application files and deploy to the existing Zeabur service.
- [ ] Verify `/api/config/status`, `/mini/tasks`, `/mini/keywords`, `/mini/stats`, and `/mini/history` return 200.
- [ ] Verify listener, Redis, runtime lock, Gemini configuration, staff count, group count, and keyword count.
- [ ] Exercise one controlled wait-task path without sending a real timeout alert, then leave the service running.
