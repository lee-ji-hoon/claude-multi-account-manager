---
description: Diagnose and repair plugin installation issues. Triggered by "repair", "fix", "troubleshoot", "check installation".
allowed-tools: [Bash, Read, Edit]
---

# Account Repair

Diagnoses the plugin installation status and automatically repairs issues.

## Instructions

Execute the checklist below in order. If a problem is found at any step, fix it immediately.

### 1. Check Accounts Directory

```bash
echo "=== 1. Accounts Directory ==="
if [ -d "$HOME/.claude/accounts" ]; then
    echo "OK: accounts directory exists"
    if [ -f "$HOME/.claude/accounts/index.json" ]; then
        echo "OK: index.json exists"
        python3 -c "import json; d=json.load(open('$HOME/.claude/accounts/index.json')); print(f'   Accounts: {len(d.get(\"accounts\",[]))}')"
    else
        echo "FAIL: index.json missing -> creating"
        echo '{"version": 1, "accounts": [], "activeAccountId": null}' > "$HOME/.claude/accounts/index.json"
    fi
else
    echo "FAIL: accounts directory missing -> creating"
    mkdir -p "$HOME/.claude/accounts"
    chmod 700 "$HOME/.claude/accounts"
    echo '{"version": 1, "accounts": [], "activeAccountId": null}' > "$HOME/.claude/accounts/index.json"
fi
```

### 2. Check Plugin Installation Status

```bash
echo "=== 2. Plugin Installation Status ==="

if [ -f "$HOME/.claude/plugins/installed_plugins.json" ]; then
    python3 -c "
import json
data = json.load(open('$HOME/.claude/plugins/installed_plugins.json'))
plugins = data.get('plugins', {})
account_plugins = {k:v for k,v in plugins.items() if 'account' in k}
if account_plugins:
    for name, entries in account_plugins.items():
        for e in entries:
            path = e.get('installPath', '?')
            ver = e.get('version', '?')
            print(f'OK: {name} v{ver}')
            print(f'   Path: {path}')
else:
    print('WARN: account plugin not registered')
"
else
    echo "WARN: installed_plugins.json not found"
fi
```

### 3. Plugin File Integrity

```bash
echo "=== 3. File Integrity ==="

INSTALL_PATH=$(python3 -c "
import json, os
path = os.path.expanduser('~/.claude/plugins/installed_plugins.json')
if os.path.exists(path):
    data = json.load(open(path))
    for name, entries in data.get('plugins', {}).items():
        if 'account' in name:
            for e in entries:
                print(e.get('installPath', ''))
                break
" 2>/dev/null | head -1)

if [ -z "$INSTALL_PATH" ]; then
    echo "FAIL: Cannot find plugin install path"
    echo "-> Please re-run install.sh"
else
    MISSING=0
    for f in account_manager.py .claude-plugin/plugin.json hooks/hooks.json hooks-handlers/session-start.sh; do
        if [ -f "$INSTALL_PATH/$f" ]; then
            echo "OK: $f"
        else
            echo "FAIL: $f missing"
            MISSING=$((MISSING + 1))
        fi
    done

    if [ -d "$INSTALL_PATH/claude_account_manager" ]; then
        echo "OK: claude_account_manager/ package"
    else
        echo "FAIL: claude_account_manager/ package missing (critical)"
        echo "-> Please re-run install.sh"
        MISSING=$((MISSING + 1))
    fi

    if [ -d "$INSTALL_PATH/skills" ]; then
        SKILL_COUNT=$(ls -d "$INSTALL_PATH/skills/"*/ 2>/dev/null | wc -l | tr -d ' ')
        echo "OK: skills/ ($SKILL_COUNT skills)"
    else
        echo "WARN: skills/ missing"
    fi

    if [ "$MISSING" -eq 0 ]; then
        echo "All files OK!"
    else
        echo "${MISSING} file(s) missing -> re-run install.sh"
    fi
fi
```

### 4. Check Keychain Token

```bash
echo "=== 4. Keychain Token ==="
python3 -c "
import subprocess, json
from datetime import datetime
result = subprocess.run(['security', 'find-generic-password', '-s', 'Claude Code-credentials', '-w'],
                       capture_output=True, text=True)
if result.returncode == 0:
    cred = json.loads(result.stdout.strip())
    oauth = cred.get('claudeAiOauth', {})
    expires_at = oauth.get('expiresAt')
    if expires_at:
        exp = datetime.fromtimestamp(expires_at / 1000)
        remaining = exp - datetime.now()
        hours = int(remaining.total_seconds() // 3600)
        mins = int((remaining.total_seconds() % 3600) // 60)
        if remaining.total_seconds() > 0:
            print(f'OK: Token valid ({hours}h {mins}m remaining)')
        else:
            print('WARN: Token expired (re-login required)')
    if oauth.get('refreshToken'):
        print('OK: Refresh token exists')
    else:
        print('FAIL: Refresh token missing (re-login required)')
else:
    print('FAIL: No credential in Keychain (login required)')
"
```

### 5. Check Duplicate Accounts

```bash
echo "=== 5. Duplicate Accounts ==="
python3 -c "
import json
index = json.load(open('$HOME/.claude/accounts/index.json'))
accounts = index.get('accounts', [])
seen = {}
duplicates = []
for acc in accounts:
    key = (acc['email'], acc.get('organizationUuid'))
    if key in seen:
        duplicates.append((acc, seen[key]))
    else:
        seen[key] = acc
if duplicates:
    print(f'WARN: {len(duplicates)} duplicate account(s) found')
    for dup, orig in duplicates:
        print(f'  Duplicate: {dup[\"id\"]} <-> {orig[\"id\"]} ({dup[\"email\"]})')
    print('-> Use /account:remove to delete unnecessary accounts')
else:
    print('OK: No duplicates')
"
```

### 6. Results Summary

After all checks are complete, summarize the results for the user:
- Number of OK items
- WARN items with recommended actions
- FAIL items requiring immediate action
