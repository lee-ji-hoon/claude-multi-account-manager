---
description: Check OAuth token status. Triggered by "check token", "token status", "token check".
allowed-tools: [Bash]
---

# Account Check

Checks the status of the current OAuth token.

## Instructions

Run the following command and **display the result to the user as-is**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" check
```

**Important**: After command execution, show the output to the user as-is without code blocks.

## Features

- Verify token validity
- Automatically attempt refresh if expired
- Display current/weekly usage
- Guide re-login if token is expired
