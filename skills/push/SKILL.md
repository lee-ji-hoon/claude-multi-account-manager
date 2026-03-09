---
description: Push account data to Telegram (sync to another Mac). Triggered by "push accounts", "push", "sync to other Mac".
allowed-tools: [Bash]
---

# Account Push

Sends all registered account data to Telegram.
You can pull it on another Mac using `/account:pull`.

## Instructions

1. Run the push command and **display the result to the user as-is**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" push
```

2. On success, inform the user that they can pull on another Mac using `/account:pull`.

**Important**: After every command execution, show the output to the user as-is without code blocks.

## Notes

- Telegram setup required: `~/.claude/hooks/telegram-config.json` (bot_token, chat_id)
- Sent data is saved as a pinned message in the Telegram chat
- Includes OAuth tokens - tokens expire after 8 hours, so pull promptly
