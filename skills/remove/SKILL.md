---
description: Delete a saved account. Triggered by "remove account", "delete account", "unregister account".
argument-hint: [account ID]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Remove

Deletes a saved account.

## Instructions

1. Check the account list and **display the result to the user as-is**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" list
```

2. If no account ID is provided as an argument:
   - Use AskUserQuestion to ask the user to select an account to delete
   - Display each account's name, Plan, and email
   - Include a "Cancel" option

3. Deletion confirmation:
   - Use AskUserQuestion to ask "Are you sure you want to delete this account?"
   - Display the account name and email

4. If confirmed, execute deletion and **display the result to the user as-is**:
```bash
echo "y" | python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" remove $ARGUMENTS
```

**Important**: After every command execution, show the output to the user as-is without code blocks.

## Notes

- Deleted accounts cannot be recovered
- Profile files and credential files are deleted together
