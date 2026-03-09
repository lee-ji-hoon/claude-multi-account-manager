---
description: Manually set an account's Plan. Triggered by "set plan", "change plan", "update plan".
argument-hint: [account ID] [Plan]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Set Plan

Manually changes an account's Plan.

## Instructions

1. Check the account list and **display the result to the user as-is**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" list
```

2. If no account ID is provided as an argument:
   - Use AskUserQuestion to ask the user to select an account

3. If no Plan is provided as an argument:
   - Use AskUserQuestion to ask the user to select a Plan
   - Options: Free, Pro, Team, Max5, Max20

4. Execute the Plan change and **display the result to the user as-is**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" set-plan $ARGUMENTS
```

**Important**: After every command execution, show the output to the user as-is without code blocks.

## Valid Plans

- Free, Pro, Team, Max5 (5 projects), Max20 (20 projects)

## Notes

- Normally, Plan is auto-detected
- Only use manual setting if auto-detection is incorrect
