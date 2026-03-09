---
description: Switch to a different account. Triggered by "switch account", "change account", "swap account".
argument-hint: [account ID]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Switch

Switches to a different Claude account.

## Instructions

1. Check the account list and **display the result to the user as-is**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" list
```

2. If no account ID is provided as an argument:
   - Use AskUserQuestion to ask the user to select an account to switch to
   - Display each account's name, Plan, email, and Organization

3. Execute the switch and **display the result to the user as-is**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" switch $ARGUMENTS
```

4. After switching, inform the user that a Claude Code restart is required.

**Important**: After every command execution, show the output to the user as-is without code blocks.

## Notes

- After switching, Claude Code must be restarted for changes to take effect
- OAuth token is automatically replaced
- Different Team accounts with the same email can be switched individually
