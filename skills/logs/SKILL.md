---
description: View token refresh logs. Triggered by "logs", "refresh history", "401 error", "token logs".
argument-hint: [export|path]
allowed-tools: [Bash]
---

# Account Logs

Views token refresh logs. You can check history of 401 errors, refresh failures, etc.

## Instructions

1. Default usage (display last 50 lines):
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" logs
```

2. If the argument is "export" (copy to Desktop):
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" logs export
```

3. If the argument is "path" (print log file path only):
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" logs path
```

**Important**: After every command execution, show the output to the user as-is without code blocks.

## Log Levels

- **ERROR** (red): Refresh failures, 401 errors, and other critical issues
- **WARN** (yellow): Token expired, missing expiresAt, and other warnings
- **INFO** (gray): Successful refreshes, token status records

## Notes

- Logs are automatically recorded at session start
- File location: `~/.claude/accounts/logs/token-refresh.log`
- Max 512KB, auto-rotated when exceeded
- Use `export` to copy to Desktop for sharing
