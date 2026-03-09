---
description: Import account from another machine. Triggered by "import account", "import".
argument-hint: [JSON or file path]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Import

Imports account information from another computer into the current Claude Code.

## Instructions

1. If an argument is provided (JSON string or file path):
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" import $ARGUMENTS
```

2. If no argument is provided:
   - Use AskUserQuestion to ask how to input the JSON:
     - "Paste unified JSON" - Directly input JSON from `/account:export`
     - "Specify file path" - Input a JSON file path
   - Run import with the provided data

3. **Display the result to the user as-is**.

**Important**: After every command execution, show the output to the user as-is without code blocks.

## Supported Formats

### Standard format (recommended)
```json
{
  "profile": { "emailAddress": "...", ... },
  "credential": { "access_token": "...", ... }
}
```

### claude_auth.json format
```json
{
  "oauthAccount": { "emailAddress": "...", ... },
  ...
}
```

## Notes

- Even with the same email, different Team/Organization accounts can be registered separately
- A notification is shown if the account duplicates an existing one
