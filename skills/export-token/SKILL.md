---
description: Export account token to CLAUDE_CODE_OAUTH_TOKEN env. Triggered by "export token", "env token", "CI token".
argument-hint: <account ID>
allowed-tools: [Bash]
---

# Account Export Token

Exports the access token of the specified account as an evaluable `export CLAUDE_CODE_OAUTH_TOKEN='...'` line on stdout.

Use the `account-export-token` zsh function wrapper for the cleanest UX (auto-evals the line into the current shell). The raw subcommand prints the line so callers can `eval $(...)` directly in scripts.

## Instructions

Run the following command and **display the result to the user as-is**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" export-token $ARGUMENTS
```

**Important**: After command execution, show the output to the user as-is without code blocks.

## Behavior

- **Long-lived token** (1-year, from `claude setup-token`): exports the token; stderr emits a `D-day` warning if within 7 days of expiry.
- **Regular OAuth token** (~8h validity): exports the current access token; stderr emits an info line that the token will expire in ~8 hours.

## Notes

- Use this when running scripts/CI inside the current shell. The token is single-quoted so `$` and other shell metacharacters are safe.
- Token appears in stdout — if shell history logging is a concern, prefer the `account-export-token` function wrapper which `eval`s the line directly and does not print the raw token.
- `CLAUDE_CODE_OAUTH_TOKEN` is overridden by `ANTHROPIC_API_KEY` in Claude Code; ensure the latter is unset for the OAuth token to take effect.
