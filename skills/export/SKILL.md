---
description: Export current account info (for transferring to another machine). Triggered by "export account", "export".
allowed-tools: [Bash]
---

# Account Export

Exports the currently logged-in account information in JSON format.
You can import it on another machine using `/account:import`.

## Instructions

1. Export the account info and **display the result to the user as-is**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" export
```

2. After export, inform the user:
   - Transfer the generated JSON securely to the other machine
   - Import on the other machine using `/account:import`

**Important**: After every command execution, show the output to the user as-is without code blocks.

## Notes

- The exported JSON contains a valid OAuth token
- Use a trusted network path for transfer
- On macOS, it is automatically copied to the clipboard
