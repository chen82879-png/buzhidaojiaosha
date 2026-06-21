# Miniapp Statistics Performance Design

## Goal

Reduce `/mini/stats` load time by removing statistics features that are no longer needed: cumulative keyword counts and recent audit records.

## Scope

- Keep today's keyword count, seven-day keyword count, open-task count, and enabled-keyword count.
- Remove the cumulative count from each keyword row.
- Remove the recent-audit section from the statistics page.
- Stop `/mini/stats` from querying recent audit records and history-check data.
- Stop keyword statistics from calculating cumulative totals and latest-message metadata.
- Preserve all existing database records, audit API behavior, history-page behavior, listener configuration, and alert rules.

## Data Flow

`/mini/stats` will request only keyword counts needed for today and the last seven days, plus open tasks. The rendered template will consume only those values. Historical hit records and rollups remain stored so existing retention and other endpoints continue to work.

## Compatibility

The repository statistics rows no longer need `total_count`, `latest_time`, `latest_chat_name`, or `latest_message_url` for the miniapp statistics page. Existing audit and history repository methods remain available to other routes.

## Testing

- Verify the statistics page still shows today, seven-day, open-task, and enabled-keyword values.
- Verify the page does not show cumulative counts or recent audit content.
- Verify `/mini/stats` does not call recent-audit or history-check repository methods.
- Run the complete test suite before deployment.
