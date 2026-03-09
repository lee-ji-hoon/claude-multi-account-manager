# multi-login-claude - Project Instructions

## Project Overview
Claude Code multi-account management plugin. Written in Python, uses macOS Keychain.

### Key Files
- `account_manager.py`: Entry point (thin wrapper)
- `claude_account_manager/`: Core package
  - `config.py`: Constants, paths, Plan limits
  - `ui.py`: Colors, formatting utilities
  - `keychain.py`: macOS Keychain integration
  - `storage.py`: File I/O (index.json, claude.json)
  - `token.py`: OAuth token management
  - `api.py`: Anthropic API calls
  - `account.py`: Account business logic
  - `commands/`: CLI command handlers
- `hooks-handlers/`: Hook scripts
- `.claude-plugin/plugin.json`: Plugin metadata
- `skills/`: Slash command skill definitions

### Release Rules

**Always use `/account:release` skill for releases!**

Release process:
1. Update `plugin.json` version (must be higher than all cached versions)
2. Commit to develop branch + create tag
3. **Merge to main branch** (required!)
4. Push main + tag
5. Verify marketplace cache update

```bash
# Check cached versions (new version must be higher)
ls ~/.claude/plugins/cache/lee-ji-hoon/account/
```

### Data Locations
- Account index: `~/.claude/accounts/index.json`
- OAuth tokens: macOS Keychain
- Profiles: `~/.claude/accounts/profile_{id}.json`
- Credentials: `~/.claude/accounts/credential_{id}.json`

### Commands
```bash
/account:list              # List accounts + usage
/account:add [name]        # Save current account
/account:switch [id]       # Switch account
/account:remove [id]       # Delete account
/account:set-plan [id] [plan]  # Set Plan
/account:check             # Check token status
/account:report            # Bug report via GitHub Issue
/account:repair            # Diagnose & fix issues
```

### Hooks
| Hook | Trigger | Action |
|------|---------|--------|
| SessionStart | Session start | Auto-register account + refresh all tokens |
| UserPromptSubmit | Message input | Refresh tokens expiring within 1 hour |

### OAuth Token Refresh
- Endpoint: `https://platform.claude.com/v1/oauth/token`
- Client ID: `9d1c250a-e61b-44d9-88ed-5944d1962f5e`
- Token validity: 8 hours (28800 seconds)
- Refresh Token: One-time use (new token issued on refresh)

### Tech Stack
- Python 3 (standard library only)
- macOS Keychain (`security` CLI)
- Claude Code Plugin System

### Testing
- Run directly: `python3 account_manager.py`
- Check usage: `/account:list`
- Check token: `/account:check`
