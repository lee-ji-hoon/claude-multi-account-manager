---
description: Pull account data from Telegram (pushed from another Mac). Triggered by "pull accounts", "pull", "sync accounts".
argument-hint: [file path]
allowed-tools: [Bash]
---

# Account Pull

Pulls account data that was sent from another Mac via `/account:push`.

## Instructions

1. Run the pull command and **display the result to the user as-is**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" pull $ARGUMENTS
```

2. After import is complete, suggest verifying with `/account:list`.

**Important**: After every command execution, show the output to the user as-is without code blocks.

## Notes

- Run without arguments: Automatically fetches from the pinned Telegram message
- Provide a file path: Imports from a local JSON file
- Already registered accounts are automatically skipped
