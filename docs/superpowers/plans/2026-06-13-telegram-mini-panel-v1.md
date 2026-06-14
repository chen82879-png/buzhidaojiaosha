# Telegram Mini Panel V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Telegram alert bot mini panel as three white-background pages: tasks, keywords, and stats.

**Architecture:** Keep the current FastAPI app and repository layer. Add a small presentation helper in `app/main.py`, replace the mini templates with a shared white shell, and route old panel URLs into the new three-page surface.

**Tech Stack:** FastAPI, Jinja2 templates, existing SQLite repository methods, existing pytest route tests, plain CSS.

---

### Task 1: Mini Panel Routes

**Files:**
- Modify: `D:\yujing\tests\test_miniapp_routes.py`
- Modify: `D:\yujing\tests\test_admin_routes.py`
- Modify: `D:\yujing\app\main.py`

- [ ] **Step 1: Write failing route tests**

Update tests so `/mini` redirects to `/mini/tasks`, `/mini/tasks` renders task cards, `/mini/keywords` renders the keyword page, `/mini/stats` renders statistics, and legacy admin routes redirect into the new pages.

- [ ] **Step 2: Verify red**

Run:

```powershell
$env:TMP='C:\Users\rog\Documents\grybuges\.tmp'; $env:TEMP='C:\Users\rog\Documents\grybuges\.tmp'; $env:PYTHONDONTWRITEBYTECODE='1'; & 'C:\Users\rog\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest D:\yujing\tests\test_miniapp_routes.py D:\yujing\tests\test_admin_routes.py -q -p no:cacheprovider
```

Expected: tests fail because `/mini/tasks` and `/mini/stats` are missing.

- [ ] **Step 3: Implement routes**

Add `mini_tasks`, `mini_stats`, and helper functions to gather open tasks, keyword statistics, and audit records. Keep `/mini/keywords` POST unchanged except for the rendered shell.

- [ ] **Step 4: Verify green**

Run the same focused tests and expect all selected tests to pass.

### Task 2: White Mini App Templates

**Files:**
- Create: `D:\yujing\app\templates\mini_shell.html`
- Create: `D:\yujing\app\templates\mini_tasks.html`
- Modify: `D:\yujing\app\templates\mini_keywords.html`
- Create: `D:\yujing\app\templates\mini_stats.html`
- Modify: `D:\yujing\app\static\styles.css`

- [ ] **Step 1: Add shared shell**

Create a shared white Telegram-style shell with bottom tabs for `任务`, `关键词`, and `统计`.

- [ ] **Step 2: Build the three pages**

Render task cards, keyword config cards, and statistic cards with empty states. Keep text concise and operational.

- [ ] **Step 3: Style only the mini surface**

Use white background, dark text, subtle borders, 8px radius, fixed bottom tab bar, and mobile-friendly spacing.

### Task 3: Deploy and Verify

**Files:**
- Modify deployment ZIP only.

- [ ] **Step 1: Run full tests**

Run:

```powershell
$env:TMP='C:\Users\rog\Documents\grybuges\.tmp'; $env:TEMP='C:\Users\rog\Documents\grybuges\.tmp'; $env:PYTHONDONTWRITEBYTECODE='1'; & 'C:\Users\rog\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 2: Deploy to Zeabur**

Package the same file set as the previous successful deployment and upload it to the existing `yujing` service.

- [ ] **Step 3: Verify production**

Check:

```text
https://gyrbuges.duckdns.org/mini/tasks
https://gyrbuges.duckdns.org/mini/keywords
https://gyrbuges.duckdns.org/mini/stats
```

Expected: all return `200` and show the white mini panel shell.
