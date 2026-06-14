# Telegram Alert Bot Design

Date: 2026-06-05

## Goal

Build a Telegram alert bot that monitors configured Telegram chats for fixed keywords, tracks whether customer messages receive a quoted reply from configured staff within a global timeout, sends one private alert to the configured staff when the timeout is missed, and provides a small configuration and statistics page.

## Confirmed Scope

- Monitor Telegram group/channel messages.
- A message enters monitoring only when both conditions are true:
  - The message belongs to an enabled configured `chat_id`.
  - The message contains one or more enabled fixed keywords for that chat rule.
- A response counts only when a configured staff member sends a Telegram reply/quoted message that references the original monitored customer message.
- Timeout duration is global for all rules.
- Timeout alert is sent once.
- Alert delivery target is the staff configured on the matching monitoring rule.
- Statistics module tracks keyword hit counts only.
- Redis is an existing external server and will be used for persistent pending-message/timeout queue state.

## Out of Scope for First Version

- Customer service performance reports.
- Average response time reports.
- Regex or multi-condition keyword rules.
- Repeated escalation reminders.
- Multi-tenant permissions.
- External business-system event ingestion.

## Architecture

Use a lightweight monolith with clear internal modules:

- `Telegram Bot Gateway`: receives Telegram webhook updates and normalizes message data.
- `Monitoring Rule Matcher`: checks enabled `chat_id` rules and fixed keyword matches.
- `Keyword Hit Recorder`: writes long-term keyword hit records into SQLite.
- `Pending Message Queue`: writes monitored messages and timeout jobs into Redis.
- `Response Detector`: detects staff reply/quote messages and marks pending messages as responded.
- `Timeout Worker`: scans due Redis timeout jobs and sends one private alert when a pending message has not been responded to.
- `Admin Web UI`: provides monitoring rule configuration and keyword hit statistics.

Data flow:

```text
Telegram message
-> chat_id and keyword rule match
-> SQLite keyword hit record
-> Redis pending message and timeout job
-> staff quoted reply closes pending message
-> timeout worker sends one private alert if still pending
```

## Technology Stack

- Python with FastAPI for webhook, API, admin page serving, and worker entrypoints.
- aiogram for Telegram Bot API integration.
- SQLite for configuration, keyword hit statistics, and alert delivery records.
- Redis for pending messages, timeout queue, and alert de-duplication.
- Built-in FastAPI static/templates for the first admin UI; no heavy frontend framework in version one.

## Admin UI

The product has two frontend surfaces:

- Web admin console for configuration, statistics, and alert delivery audit.
- Telegram Mini App for on-duty staff to quickly inspect their relevant alerts and rules.

### Design System

- Visual style: dark operations dashboard.
- Background: `#020617`.
- Primary panels: `#0F172A`.
- Secondary panels: `#1E293B`.
- Primary text: `#F8FAFC`.
- Muted text: `#94A3B8`.
- Accent/status colors:
  - Normal/success: `#22C55E`.
  - Warning: `#F59E0B`.
  - Timeout/error: `#EF4444`.
- Typography:
  - Main UI text: Fira Sans with a system sans fallback.
  - Numeric ids, counters, timestamps, and message ids: Fira Code or a system monospace fallback.
- Icon style: Lucide-style line icons. Do not use emoji as structural icons.
- Shape system: 6-8px radius for tool surfaces and repeated cards.
- Interaction system:
  - Every async action has loading state.
  - Every destructive action has confirmation.
  - Every icon-only action has an accessible label and tooltip on web.
  - Touch targets are at least 44px in the Mini App.

### Web Admin Console

The first web admin console has three main pages.

### Monitoring Rule Configuration

This is the primary admin page. Each rule shows and edits one monitored chat:

- `chat_id`
- group display name
- enabled/disabled state
- fixed keyword list
- per-keyword enabled/disabled state
- configured staff recipients for timeout alerts
- per-staff enabled/disabled state

The page should make the relationship visible in one place:

```text
Which chat -> which keywords -> which staff receive timeout alerts
```

Each rule appears as a compact expandable row:

- Left: group name, `chat_id`, enabled status.
- Middle: enabled keyword chips and disabled keyword count.
- Right: enabled staff chips and latest alert state.
- Actions: edit, duplicate, disable.

Rule editing happens in a right-side drawer:

- Group information section.
- Fixed keyword list section with batch paste/import.
- Staff recipient section with `telegram_user_id`, username, display name, and enabled state.
- Sticky save area at the drawer bottom.
- Save button is disabled while saving and shows clear success/error feedback.

Batch keyword import shows a parse preview before saving:

- new keywords count
- duplicate keywords count
- invalid line count

### Statistics Overview

The statistics page tracks keyword hit counts:

- total hits for selected time range
- hits grouped by chat
- hits grouped by keyword
- filters by date/time range
- optional filter by chat

The first version does not show staff response metrics.

Recommended chart patterns:

- Trend over time: line chart grouped by hour or day.
- Keyword ranking: horizontal bar chart sorted descending.
- Chat ranking: horizontal bar chart sorted descending.
- When chart data fails to load, show a recoverable error state with retry, not an empty chart.

### Alert Delivery Records

The alert records page supports operational troubleshooting:

- timestamp
- group name and `chat_id`
- matched keyword list
- original message link
- target staff
- delivery status
- Telegram API error message when private message delivery fails

Filters:

- time range
- group
- keyword
- delivery status

## Telegram Mini App

The Mini App is optimized for on-duty staff. It should not duplicate the full admin console.

Bottom navigation has three tabs.

### Today

Shows the staff member's current operational view:

- today's keyword hit count for rules where this staff member is assigned
- recent timeout alerts
- recent keyword hits

Each alert row shows:

- group name
- matched keyword list
- original message time
- alert status
- button to open the original Telegram message

### Rules

Shows the rules assigned to the current staff member:

- group name and `chat_id`
- keyword list
- whether the rule is enabled

Normal staff see this as read-only. Admin users may later receive editing controls, but first version can keep Mini App rule editing read-only.

### Me

Shows the staff member's Telegram identity and delivery readiness:

- Telegram display name
- Telegram username
- Telegram user id
- whether this user exists in the staff identity database
- latest private-message delivery status
- recent alert delivery records for this user

### Mini App Detail Screen

The alert detail screen shows:

- status label, such as `15 分钟无客服回复`
- group name and `chat_id`
- matched keyword list
- original message time
- original message excerpt
- target staff recipient
- original message link

Primary action:

- `打开原消息`

Secondary action:

- `复制链接`

Mini App layout must respect Telegram safe areas and avoid hiding scroll content behind the bottom navigation.

## SQLite Data Model

### `monitor_rules`

- `id`
- `chat_id`
- `chat_name`
- `enabled`
- `created_at`
- `updated_at`

### `rule_keywords`

- `id`
- `rule_id`
- `keyword`
- `enabled`
- `note`
- `created_at`
- `updated_at`

### `rule_staff`

- `id`
- `rule_id`
- `telegram_user_id`
- `telegram_username`
- `display_name`
- `enabled`
- `created_at`
- `updated_at`

### `keyword_hits`

- `id`
- `rule_id`
- `chat_id`
- `chat_name`
- `message_id`
- `telegram_user_id`
- `telegram_username`
- `matched_keyword`
- `message_excerpt`
- `message_url`
- `message_time`
- `created_at`

### `alert_deliveries`

- `id`
- `rule_id`
- `chat_id`
- `message_id`
- `matched_keyword`
- `staff_telegram_user_id`
- `staff_telegram_username`
- `staff_display_name`
- `status`
- `error_message`
- `sent_at`
- `created_at`

### `settings`

- `key`
- `value`
- `updated_at`

Required setting:

- `global_timeout_minutes`

## Redis Model

### Pending Message

Key:

```text
pending:{chat_id}:{message_id}
```

Value:

```json
{
  "rule_id": 1,
  "chat_id": "-1001571955528",
  "chat_name": "Group Name",
  "message_id": 398744,
  "message_time": "2026-06-04T21:11:25+08:00",
  "matched_keywords": ["keyword"],
  "message_excerpt": "original message excerpt",
  "message_url": "https://t.me/c/1571955528/398744",
  "status": "pending"
}
```

### Timeout Queue

Sorted set:

```text
timeout_queue
```

Member:

```text
{chat_id}:{message_id}
```

Score:

```text
unix timestamp when timeout becomes due
```

### Alert De-Duplication

Key:

```text
alerted:{chat_id}:{message_id}
```

This key prevents repeat timeout alerts. It should be set before or during alert send processing so retried worker runs do not duplicate the same alert.

## Keyword Matching

- Use fixed substring matching for the first version.
- Match only enabled keywords belonging to the enabled monitor rule for the incoming `chat_id`.
- If a message matches multiple keywords, record each keyword hit for statistics.
- For timeout tracking, create one pending message task per original message. The pending task stores all matched keywords so the alert can show the full keyword list.

## Response Detection

A message closes a pending task only when all conditions are true:

- The sender is an enabled staff member on the same monitoring rule.
- The message is a Telegram reply/quoted message.
- The quoted original message id matches a Redis pending message in the same chat.

Non-staff replies do not close the pending task. Staff messages that are not replies/quotes do not close the pending task.

## Timeout Alert Behavior

- Timeout worker scans `timeout_queue` for due members.
- For each due member, load `pending:{chat_id}:{message_id}`.
- If the pending message no longer exists or is marked responded, remove the queue member.
- If it is still pending and no `alerted:{chat_id}:{message_id}` exists, send private alerts to enabled staff on the matching rule.
- Send only once per monitored message.
- Record delivery success or failure in `alert_deliveries`.
- If Telegram refuses the private message, record the failure reason and keep the alert as attempted.

## Alert Template

```text
接收人员：{staff_display_name}{private_message_status} (@{staff_username})
关键词：{matched_keywords}
群组：{chat_name_or_chat_id}
时间：{message_time}
状态：客户消息 {global_timeout_minutes} 分钟无客服回复
原因：客户消息未被客服身份库中的人员引用或跟进
原消息链接：打开原消息 ({message_url})
```

Example private-message failure marker:

```text
【拒绝私聊】
```

## Telegram Message URL Rules

- Public chat/channel with username:

```text
https://t.me/{chat_username}/{message_id}
```

- Private supergroup/channel internal link:

```text
https://t.me/c/{internal_chat_id_without_-100_prefix}/{message_id}
```

The system should generate the link from chat configuration and incoming Telegram metadata.

## Deployment

Run one service process that includes:

- FastAPI webhook/API/admin server.
- Background timeout worker.

Environment variables:

- `TELEGRAM_BOT_TOKEN`
- `WEBHOOK_URL`
- `REDIS_URL`
- `SQLITE_PATH`
- `ADMIN_PASSWORD`
- `GLOBAL_TIMEOUT_MINUTES` as initial default, then editable in `settings`

Redis is provided by an existing server. Redis should have AOF persistence enabled.

## Testing Plan

Automated tests should cover:

- Disabled `chat_id` rules are ignored.
- Enabled `chat_id` plus enabled keyword creates a keyword hit.
- Keyword hit creates a Redis pending message and timeout queue entry.
- Non-staff quoted replies do not close pending messages.
- Staff non-quoted messages do not close pending messages.
- Staff quoted reply to the original message closes the pending message.
- Due pending message sends exactly one alert.
- Re-running timeout worker after alert does not send duplicates.
- Telegram private-message failure is recorded in `alert_deliveries`.
- Keyword hit statistics aggregate by chat, keyword, and time range.

## Open Operational Notes

- The first keyword list will be provided later and imported into the monitoring rule configuration.
- The first deployment target is not specified yet; the implementation should keep deployment simple and portable.
- Git commit for this design document is skipped in the current environment because `git` is not available on PATH.
