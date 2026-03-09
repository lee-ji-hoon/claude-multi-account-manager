---
description: Show registered accounts with usage. Triggered by "list accounts", "show accounts", "account list".
allowed-tools: [Bash]
---

# Account List

Displays all registered Claude accounts with real-time usage.

## Instructions

Run the following command and **display the result to the user as-is**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" list
```

**Important**: After command execution, show the output to the user as-is without code blocks.

## Features

- Display all registered accounts (with Team/Organization distinction)
- Current session / weekly usage progress bar
- Time remaining until reset
- Time remaining until token expiration
