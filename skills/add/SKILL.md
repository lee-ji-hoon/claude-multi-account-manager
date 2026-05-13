---
description: Save the currently logged-in account. Triggered by "add account", "save account", "register account".
argument-hint: [name]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Add

Saves the currently logged-in Claude account.

## Instructions

1. Run the add command and **display the result to the user as-is**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" add $ARGUMENTS
```

2. If the message "Account already registered" is displayed:
   - Use AskUserQuestion to present the following options:
     - "Refresh token only" - Update with the current Keychain token
     - "Re-login and refresh" - Guide to /login
     - "Cancel"

3. Execute based on the selection and **display the result to the user as-is**:
   - If "Refresh token only" is selected:
     ```bash
     echo "1" | python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" add
     ```
   - If "Re-login" is selected: Guide to run /login and retry

**Important**: After every command execution, show the output to the user as-is without code blocks.

## Notes

- Plan is auto-detected from the credential (rateLimitTier, subscriptionType)
- If the name is omitted, it is auto-generated from displayName or email
- Even with the same email, different Team/Organization accounts are registered separately
