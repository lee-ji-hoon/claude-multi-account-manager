# Switchboard project guidance

Switchboard is currently a Claude Code account plugin plus a native macOS
menu-bar prototype for Claude, Codex, Grok, and Gemini/Antigravity monitoring.
The plugin remains under `.claude-plugin/`; the desktop prototype lives under
`prototype/switchboard-menubar/`.

## Ground truth

- Claude account data: `~/.claude/accounts/` and macOS Keychain.
- Codex account data: read through `claude_account_manager/codex_provider.py`.
- Grok usage: local Grok TUI `/usage`; do not send it as a model prompt.
- Gemini quota and credits: `agy --print "/usage"` and
  `agy --print "/credits"`. Treat AGY as the only Gemini provider surface;
  legacy Gemini CLI account metadata is outside Switchboard's contract.
- Anthropic OAuth refresh endpoint: `https://platform.claude.com/v1/oauth/token`.
  Refresh tokens rotate once; a refreshed credential is usable only after its
  Keychain or account-file write succeeds.

## Verification

Run `python3 -m unittest discover -s tests -p 'test_*.py'` for Python changes.
For the menu-bar prototype, also run
`prototype/switchboard-menubar/run.sh --preview` and inspect the rendered app.
Treat live usage output as allowlisted data: credential and token fields must
never enter the snapshot.

## Releases

For every release or deployment, first read `docs/RELEASING.md`, then follow
`skills/release/SKILL.md`. `scripts/release_notes.py` is the executable
release-note and README-impact gate. A release that modifies either README must
stage both README files with the version metadata and changelog.
