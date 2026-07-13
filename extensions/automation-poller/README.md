# Grybuges Automation Poller

This is the first browser-extension polling version for the Telegram alert bot.
It does not contain third-party business automation yet. The current supported
action is `echo`, which verifies the full loop:

1. Backend creates an automation command.
2. Chrome extension long-polls `/api/automation/poll`.
3. Extension runs the command.
4. Extension posts the result to `/api/automation/result`.

## Install locally

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Choose Load unpacked.
4. Select this folder: `extensions/automation-poller`.
5. Open the extension popup.
6. Set Backend URL to `https://gyrbuges.duckdns.org`.
7. Set Automation Secret to the server `AUTOMATION_SECRET`.
8. Enable polling.

## Test command

Create a command from a trusted terminal or admin client:

```bash
curl -X POST "https://gyrbuges.duckdns.org/api/automation/commands?secret=YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"action":"echo","payload":{"text":"hello"}}'
```

After the extension polls and finishes it, check status:

```bash
curl "https://gyrbuges.duckdns.org/api/automation/commands/COMMAND_ID?secret=YOUR_SECRET"
```
