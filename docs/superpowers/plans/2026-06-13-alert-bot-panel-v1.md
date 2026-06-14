# Alert Bot Panel V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old multi-page panel with the new design's first-version surface: a status page, fixed keyword configuration, audit/wait JSON APIs, and webhook.

**Architecture:** Keep the existing FastAPI app, Telegram listener, webhook, Redis queue, SQLite repository, and Zeabur deployment. Remove old visible page routes from the public surface and add small JSON/status endpoints that read through existing repository methods when available.

**Tech Stack:** FastAPI, Jinja2 templates, pytest, existing SQLite repository, existing Zeabur Docker deployment.

---

### Task 1: Route Surface Tests

**Files:**
- Modify: `D:\yujing\tests\test_admin_routes.py`
- Modify: `D:\yujing\tests\test_miniapp_routes.py`

- [ ] Write tests asserting `/` returns the new status page, `/api/audit/recent` returns JSON, `/api/wait/pending` returns JSON, `/admin/keywords` redirects to `/mini/keywords`, and old visible routes return 404.
- [ ] Run focused route tests and verify they fail on the current implementation.

### Task 2: Route Surface Implementation

**Files:**
- Modify: `D:\yujing\app\main.py`
- Create: `D:\yujing\app\templates\status.html`
- Modify: `D:\yujing\app\templates\mini_keywords.html`

- [ ] Replace `/` redirect with a status dashboard template.
- [ ] Add `/api/audit/recent` and `/api/wait/pending`.
- [ ] Remove old visible routes: `/admin`, `/admin/rules`, `/admin/alerts`, `/mini`, `/mini/rules`, `/mini/me`.
- [ ] Keep `/admin/keywords`, `/mini/keywords`, `POST /mini/keywords`, and `/webhook/telegram`.
- [ ] Remove old mini bottom tabs from the fixed keyword page.

### Task 3: Verification And Deploy

**Files:**
- No code files beyond Tasks 1-2.

- [ ] Run the full pytest suite.
- [ ] Package with forward-slash zip paths.
- [ ] Upload to Zeabur existing `yujing` service.
- [ ] Verify `https://gyrbuges.duckdns.org/`, `/mini/keywords`, `/api/audit/recent`, and `/api/wait/pending`.
