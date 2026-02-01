# Changelog

All notable changes to this project will be documented in this file.

## [0.0.1] - 2026-02-01

### What's changed

**Added**
- Initial release of Claude Code multi-account manager plugin
- Multiple account management without logout (`/account:add`, `/account:switch`, `/account:remove`)
- Real-time usage monitoring with visual progress bars
- Automatic token refresh for all accounts on session start
- Plan auto-detection (Free / Pro / Team / Max5 / Max20)
- SessionStart hook for automatic account registration
- macOS Keychain integration for secure token storage

**Technical Details**
- OAuth token refresh via `platform.claude.com/v1/oauth/token`
- Refresh token rotation (single-use tokens)
- Token validity: 8 hours (28800 seconds)

### Commits

```
b360843 feat: Initial release - Claude Code multi-account manager plugin
deef16d fix: Correct SessionStart hook configuration format
6121cff docs: Update installation to plugin-based approach
eb40c43 docs: Add marketplace installation method
404c682 refactor: Simplify command structure and add marketplace support
03c0a04 feat: Always refresh all account tokens on session start
efad03b fix: Use correct OAuth endpoint for token refresh
e8dd30c docs: Add architecture documentation with diagrams
092bb67 docs: Add both dialog and terminal installation methods
2c4c8a4 docs: Update README with new command structure
b96b08b docs: Simplify README with Mermaid diagram
```

### Full Changelog

https://github.com/lee-ji-hoon/claude-multi-account-manager/commits/main
