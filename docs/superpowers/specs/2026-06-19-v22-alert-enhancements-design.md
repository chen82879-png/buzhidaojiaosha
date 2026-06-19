# V22 Alert Enhancements Design

## Scope

This change is based on the stable v22 baseline (`b04cb6e`). It adds three alert-system improvements without adding business automation or shift-based history scanning:

1. Separate keyword statistics, task creation, and timeout alert switches.
2. Send one severe alert when a timed-out task remains open for another 10 minutes.
3. Cancel every related task when any linked Telegram message is deleted.

It also formalizes a completed-task acknowledgement rule: after staff has answered and the task is completed, a customer acknowledgement message must not create a new wait, follow-up, reply, or self-reply task.

## Keyword Control Layers

Each of the 18 fixed keywords has three persisted switches:

- `stats_enabled`: matching messages are counted in keyword statistics.
- `task_enabled`: matching staff replies create wait tasks and participate in task flows.
- `alert_enabled`: timed-out tasks send Telegram alerts.

The dependency rules are:

- Statistics can remain enabled independently.
- Disabling task creation automatically disables timeout alerts.
- Enabling timeout alerts automatically enables task creation.
- Recipient Chat IDs are used only when alerts are enabled.
- Existing v22 keyword configuration is migrated with all three switches preserving current behavior.

Matching remains limited to the existing 18 fixed keywords and configured monitoring groups.

## Severe Timeout Alert

When a task reaches its normal timeout:

1. The worker sends the current timeout alert once.
2. The task remains open with its first-alert timestamp recorded.
3. A severe-alert due time is set to 10 minutes after the first alert.
4. If the task is still open at that time, the worker sends one severe timeout alert.
5. The task records the severe-alert timestamp so restarts and repeated worker passes cannot resend it.

Completion, deletion, or cancellation before the severe due time prevents the severe alert. The severe alert uses the task's existing recipients and message link.

This applies to wait, follow-up, reply, and self-reply tasks. It does not change their first timeout durations.

## Deleted Message Cancellation

Every task keeps context links for its root, trigger, wait, follow-up, and later related messages. When Telegram reports a deleted message:

1. Find all open tasks linked to that chat and message ID.
2. Mark each task `deleted` in SQLite.
3. Remove its Redis pending and severe-alert queue entries.
4. Exclude it from open lists, keyword statistics, closure statistics, and anomaly counts.
5. Keep its deleted snapshot for audit display for three days.
6. Remove the snapshot during the existing three-day detail cleanup.

The same path handles wait, follow-up, reply, and self-reply tasks. The deletion handler is idempotent: processing the same Telegram deletion twice has no additional effect.

## Completed Acknowledgement Exclusion

The acknowledgement set is:

- `1`
- `好的`
- `明白`
- `谢谢`
- `ok`
- `知道了`

Comparison removes surrounding whitespace and punctuation and ignores Latin letter case. It is an exact normalized-message match, not a substring match.

When staff has already answered and the related task is completed, a later customer acknowledgement remains completed and creates no new task. This applies whether the acknowledgement:

- directly replies to a staff message;
- replies to the original customer message;
- or is sent without a Telegram reply reference in the same monitored conversation.

For an unreferenced acknowledgement, the system only suppresses task creation; it does not reopen or modify unrelated tasks. Messages such as account numbers containing `1` or words containing `ok` are not excluded.

## Data Model

`keyword_configs` gains:

- `stats_enabled INTEGER NOT NULL DEFAULT 1`
- `task_enabled INTEGER NOT NULL DEFAULT 1`

`alert_enabled` remains the third switch.

`monitor_tasks` gains:

- `first_alert_sent_at TEXT`
- `severe_due_at TEXT`
- `severe_alert_sent_at TEXT`

The Redis queue uses a distinct severe-alert member/key namespace so the normal and severe deliveries cannot collide.

## UI

The keyword page keeps the current white layout and displays three compact switches for each keyword: statistics, task, and alert. Recipient Chat IDs remain on the same row or detail block.

Dependencies are enforced in both the browser and API. The API remains authoritative if a client sends an invalid combination.

Task pages keep their current layout. Severe timeout state is shown as a status label; no new page is added.

## Failure Handling

- SQLite is the source of truth for task state and alert timestamps.
- Redis queue loss is recoverable because the worker reconstructs due work from SQLite.
- Telegram send failures do not mark an alert as delivered; the worker may retry on a later pass.
- A successful first or severe alert is recorded before the queue member is removed.
- Deleted and completed tasks are checked immediately before every alert send.

## Testing

Automated tests cover:

- all valid three-switch combinations and API dependency normalization;
- statistics-only keyword matches;
- task creation without alert delivery;
- standard alert followed by one severe alert after 10 minutes;
- no severe alert after completion or deletion;
- restart/idempotency behavior for severe alerts;
- deletion cancellation for wait, follow-up, reply, and self-reply tasks;
- Redis queue cleanup after deletion;
- deleted records excluded from statistics and history totals;
- acknowledgement suppression for referenced and unreferenced customer messages;
- non-exact text such as account numbers containing `1` is not suppressed;
- preservation of the existing 18 keywords, monitoring groups, recipients, and v22 behavior.

## Out Of Scope

- Shift-based history detection.
- AI/Gemini decisions.
- Business automation, automatic replies, spreadsheet synchronization, or browser extension work.
- Changes to monitoring group IDs, bot token, Telegram login session, or existing recipient Chat IDs.
