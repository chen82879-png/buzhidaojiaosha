# Miniapp Statistics Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove cumulative keyword counts and recent audit work from `/mini/stats` while preserving today's and seven-day statistics.

**Architecture:** Keep historical storage and unrelated endpoints unchanged. Narrow the statistics repository result to current display requirements, narrow `build_mini_stats` to required data sources, and remove unused template sections.

**Tech Stack:** Python 3, FastAPI, Jinja2, SQLite, pytest

---

### Task 1: Lock the reduced statistics contract

**Files:**
- Modify: `tests/test_miniapp_routes.py`

- [ ] **Step 1: Write a failing route test**

Update the statistics-page repository double so `recent_audit_records` and `history_check_summary` raise `AssertionError` if called. Assert that the response contains today's and seven-day values but does not contain `累计`, `最近审计`, or audit message text.

- [ ] **Step 2: Run the focused route test**

Run: `D:\ptyhon\python.exe -m pytest tests/test_miniapp_routes.py::test_mini_stats_page_displays_keyword_statistics_without_audit_or_totals -q -p no:cacheprovider`

Expected: FAIL because the current page calls the forbidden repository methods or renders removed content.

- [ ] **Step 3: Write a failing repository test**

Update `tests/test_repositories.py` to assert that each `keyword_statistics()` row contains `today_count` and `seven_day_count`, and excludes `total_count`, `latest_time`, `latest_chat_name`, and `latest_message_url`.

- [ ] **Step 4: Run the focused repository test**

Run: `D:\ptyhon\python.exe -m pytest tests/test_repositories.py -k keyword_statistics -q -p no:cacheprovider`

Expected: FAIL because the current rows expose cumulative and latest-message fields.

### Task 2: Remove unnecessary statistics work

**Files:**
- Modify: `app/main.py`
- Modify: `app/repositories.py`
- Modify: `app/templates/mini_stats.html`
- Test: `tests/test_miniapp_routes.py`
- Test: `tests/test_repositories.py`

- [ ] **Step 1: Narrow `build_mini_stats`**

Remove latest-time formatting, `total_count`, `audit_records`, and `history_check` from the returned page context. Keep keyword statistics and open-task counting unchanged.

- [ ] **Step 2: Narrow `Repository.keyword_statistics`**

Calculate only today's and seven-day counts. Remove cumulative aggregation and latest-message lookup while retaining deleted-message exclusion.

- [ ] **Step 3: Simplify the template**

Remove the per-keyword cumulative metric, recent-message metadata, and entire recent-audit section. Keep today's and seven-day keyword metrics.

- [ ] **Step 4: Run focused tests**

Run: `D:\ptyhon\python.exe -m pytest tests/test_miniapp_routes.py tests/test_repositories.py -q -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 5: Commit the implementation**

Commit message: `perf: simplify mini stats queries`

### Task 3: Verify and deploy

**Files:**
- No source changes expected

- [ ] **Step 1: Run complete verification**

Run: `D:\ptyhon\python.exe -m pytest -q -p no:cacheprovider`

Run: `D:\ptyhon\python.exe -m compileall -q app`

Expected: all tests pass and compilation exits with code 0.

- [ ] **Step 2: Confirm protected configuration is unchanged**

Verify no diff exists for `app/monitor_groups.py`, `app/config.py`, or `.env.example`.

- [ ] **Step 3: Deploy to the existing Zeabur service**

Upload the verified project package to the existing service and environment without replacing persistent environment variables or listener session storage.

- [ ] **Step 4: Verify production**

Check `https://gyrbuges.duckdns.org/mini/stats` and `/api/config/status`. Confirm the statistics page responds successfully, preserves today/seven-day metrics, and omits cumulative and recent-audit content.
