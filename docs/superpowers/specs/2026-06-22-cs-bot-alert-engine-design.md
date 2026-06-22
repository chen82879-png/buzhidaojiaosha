# CS Bot Alert Engine Design

## Objective

Replace the current alert state machine with a behavior-equivalent implementation of the alert and alert-related AI logic from `mingf848-hue/cs-bot` commit `a1da1e886f18fc376cdfef6789f2ac00d65ebdfa`.

Keep the existing Telegram credentials, monitored groups, bot token, alert recipients, keyword configuration, white miniapp, message snapshots, and statistics. Exclude Zendesk integration, customer auto-replies, private AI replies, Chrome extension behavior, and all business automation.

## Architecture

The application keeps its current FastAPI miniapp and Telegram listener. A dedicated in-memory alert engine owns four task pools: wait, follow-up, missed reply, and self-reply. The engine follows the source project's trigger, replacement, completion, timeout, deletion, and routing behavior.

SQLite continues storing message snapshots, statistics, and history-analysis results. Redis continues storing runtime locks, Telegram sessions, and keyword alert configuration. Neither SQLite nor Redis restores active countdown tasks after restart.

## Preserved Application Surface

- Existing Telegram API ID, API hash, login session, bot token, and listener account.
- Existing 11 monitored groups.
- Existing 18 wait keywords and per-keyword alert routes.
- Existing white miniapp pages: Tasks, Keywords, Statistics, and History.
- Existing message snapshot and statistics data.
- Existing custom domain and Zeabur service.

No fifth configuration page is added.

## Staff Recognition

A sender is staff when any of these checks succeeds, in this order:

1. The sender ID is the active Telegram listener account ID.
2. The sender ID is present in `OTHER_CS_IDS`.
3. The normalized display name exactly matches a configured staff name.
4. The display name starts with `YY_6/9_值班号` or `Y_YY`.

The initial explicit staff identities are:

| Telegram ID | Display name |
| ---: | --- |
| 7511822833 | Y_YY_grybuges |
| 6239545703 | Y_YY_Xankas 阿诺 |
| 6986253280 | Y_YY_Belxiron |
| 7456405913 | Y_YY_Zillmann 阿布 |
| 8714311708 | Y_YY_ARATAKITO |
| 5821810621 | Y_YY_wladyslaw |
| 5361809424 | YY_6/9_值班号2【拒绝私聊】 |
| 5317794797 | YY_6/9_值班号3【拒绝私聊】 |
| 6728235813 | YY_6/9_值班号6【拒绝私聊】 |
| 5583181496 | YY_6/9_值班号⑤ |
| 7126762659 | YY_6/9_值班号7【拒绝私聊】 |
| 5229932672 | YY_6/9_值班号➊ |
| 5787870260 | YY_6/9_值班号4【拒绝私聊】 |

The first 12 IDs were matched from the production message snapshot database. ID `5361809424` was supplied by the operator because no matching snapshot was found for duty account 2.

## Real-Time State Machine

### Wait

- Trigger only when recognized staff explicitly replies to a customer message and the reply matches an enabled wait keyword.
- Start a 12-minute countdown from the staff reply timestamp.
- A new wait-keyword reply for the same flow replaces the prior wait task and restarts 12 minutes.
- A follow-up keyword converts the wait task to a follow-up task.
- A normal staff result in the related flow completes the task.
- At 12 minutes, send the first wait-timeout alert.
- Ten minutes after the first alert, send one severe wait-timeout alert if the flow remains unresolved.

### Follow-Up

- Trigger only when recognized staff replies with an exact configured follow-up keyword and the related flow contains an alert-enabled wait keyword.
- Start a 15-minute countdown.
- Another follow-up keyword replaces the task and restarts 15 minutes.
- A wait keyword converts the task back to a wait task and starts a new 12-minute countdown.
- A normal staff result in the related flow completes the task.
- Customer follow-up does not close or replace the follow-up countdown.
- At 15 minutes, send one follow-up timeout alert.

### Missed Reply

- Trigger only when a customer explicitly replies to a recognized staff message.
- The related flow must contain an alert-enabled wait keyword.
- Do not create a task when the customer message exactly matches an ignore keyword.
- Start a five-minute countdown.
- A recognized staff reply to the customer message completes the task.
- A normal staff response in the same related message flow also completes the task.
- Wait or follow-up responses transition to their corresponding task type instead of completing the business flow.
- At five minutes, send one missed-reply alert.
- Do not add global monitoring for unreferenced customer messages.

### Self-Reply

- Trigger when a customer replies to their own prior message in a flow containing an alert-enabled wait keyword.
- Do not create a task when the new message exactly matches an ignore keyword.
- Deduplicate Telegram media albums so one album creates at most one task.
- Start a three-minute countdown.
- A recognized staff response in the related flow completes the task.
- At three minutes, send one self-reply alert.

## Task Replacement and Correlation

- Each customer message and message flow is tracked independently.
- A newer wait task for the same source message replaces the prior wait task.
- Wait and follow-up tasks replace one another during state transitions.
- A newer missed-reply message in the same flow replaces the previous missed-reply task.
- Media albums create only one missed-reply or self-reply task.
- A related flow includes the customer source message, staff wait/follow-up messages, trigger message, Telegram reply target, topic root, and recorded related message IDs.
- A normal staff response to any valid related message can complete the flow, matching source-project behavior.

## Message Deletion

Deleting any task-related message cancels the corresponding active task:

- Customer source message.
- Staff wait or follow-up trigger message.
- Customer missed-reply or self-reply trigger message.
- Any recorded related flow message used by the active task.

If deletion occurs after the first wait alert, the severe alert must not be sent. Deletion affects only the related task flow.

## Ignore Keywords

Use normalized exact matching, not substring matching. Preserve the source project's default ignore list:

`好, 1, 不用了, 到了, 好的, 谢谢, 收到, 明白, 好的谢谢, ok, 好滴, 好的呢, 嗯, 嗯嗯, 谢了, okk, k, 行, 妥, 了解, 已收, 没问题, 好的收到, ok了, 麻烦了, 好的感谢, 哦, 知道了, 好的知道了, 没事了`

Ignore keywords prevent customer-generated missed-reply and self-reply tasks. They do not disable staff wait or follow-up keywords.

## Alert Routing

- Each wait keyword can independently enable or disable timeout alerts.
- Each wait keyword can have its own recipient Chat IDs.
- Wait, severe wait, follow-up, missed-reply, and self-reply alerts inherit the recipient route of the flow's wait keyword.
- When no keyword-specific route exists, fall back to the global alert recipients.
- Staff recognition and alert recipients are independent concerns.

## Work Mode

- Preserve `上班`, `下班`, and `状态` controls.
- While stopped, continue recording message snapshots but create no alert tasks.
- Entering off-duty mode cancels every active in-memory countdown.
- Returning to work processes only new messages and does not recreate tasks from off-duty messages.
- Entering off-duty mode runs the source project's history audit before clearing runtime state.

## AI and Historical Detection

Use Gemini through `GEMINI_API_KEY` and configurable `GEMINI_MODEL`, with the source default `gemini-3.5-flash`.

Preserve alert-related AI behavior:

- Decide whether a customer's latest message still requires a reply.
- Decide whether unreferenced messages after a referenced message are continuation details or independent new questions.
- Detect unhandled messages across all monitored groups.
- Treat explicit staff replies as hard closure evidence and use AI for ambiguous context.
- Preserve whitelist-request, leader-approval, approval-follow-up, and `同意后处理` detection.
- Run the off-duty audit over the source project's recent 10-hour window, reading up to 3,000 messages per group.
- Use a 12-hour lookback for ordinary manual keyword checks and a 20-hour lookback for full checks, reading up to 6,000 messages per group.
- Preserve the source audit exclusions for groups `-1002807120955` and `-1002169616907`.
- Skip service messages, stickers, and GIF-only entries where the source project skips them.

AI failures use conservative source behavior:

- Reply-needed failure means the message needs manual review.
- Orphan-context failure is not exempted.
- Continuation-classification failure is treated as a new question.

Exclude AI customer replies, private-chat AI, Zendesk actions, browser-extension actions, and automated business execution.

## Miniapp

### Tasks

Show active in-memory wait, follow-up, missed-reply, and self-reply tasks with remaining time and source links. Restarting, suspending, or entering off-duty mode clears this page's active tasks.

### Keywords

Continue managing the 18 wait keywords, alert enablement, and per-keyword recipient Chat IDs.

### Statistics

Keep today's hits, seven-day hits, open-task count, enabled-keyword count, and keyword ranking.

### History

Show keyword closure checks, full AI missed-message detection, off-duty audit results, and anomaly details.

## Failure Handling

- A confirmed Telegram deletion cancels the related task.
- A Telegram message-existence check failure assumes the message still exists to avoid suppressing an alert.
- A Gemini failure produces a manual-review result and never silently closes the item.
- A bot delivery failure is logged and is not automatically retried, matching the source project.
- A distributed runtime lock prevents duplicate Telegram listener instances.
- If the Telegram session is invalid, keep the web application available and stop message monitoring.

## Verification

Automated tests must cover:

- Every trigger, transition, replacement, completion, timeout, and deletion path for all four real-time task types.
- Exact 12-minute, 22-minute, 15-minute, five-minute, and three-minute alert timing.
- Staff recognition by listener ID, explicit ID, exact name, and prefix.
- Exact ignore-word matching and album deduplication.
- Per-keyword recipient routing and global fallback.
- AI closure, orphan detection, continuation classification, approval workflows, and conservative failure behavior.
- Off-duty audit and work-mode transitions.
- Runtime task loss after restart.
- Absence of Zendesk, automated replies, Chrome-extension behavior, and business automation.

Production verification must confirm the listener session, 11 monitored groups, 18 keywords, bot delivery, miniapp pages, runtime lock, and Gemini connectivity before the service is considered ready.
