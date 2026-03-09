---
name: account:repair
description: 플러그인 설치 문제 진단 및 수리. "수리", "repair", "문제 해결", "설치 확인" 요청 시 사용.
allowed-tools: [Bash, Read, Edit]
---

# Account Repair

플러그인 설치 상태를 진단하고 문제를 자동으로 수리합니다.

## Instructions

아래 체크리스트를 순서대로 실행하세요. 각 단계에서 문제가 발견되면 즉시 수정합니다.

### 1. 계정 디렉토리 확인

```bash
echo "=== 1. 계정 디렉토리 ==="
if [ -d "$HOME/.claude/accounts" ]; then
    echo "OK: accounts 디렉토리 존재"
    if [ -f "$HOME/.claude/accounts/index.json" ]; then
        echo "OK: index.json 존재"
        python3 -c "import json; d=json.load(open('$HOME/.claude/accounts/index.json')); print(f'   계정 수: {len(d.get(\"accounts\",[]))}개')"
    else
        echo "FAIL: index.json 없음 → 생성"
        echo '{"version": 1, "accounts": [], "activeAccountId": null}' > "$HOME/.claude/accounts/index.json"
    fi
else
    echo "FAIL: accounts 디렉토리 없음 → 생성"
    mkdir -p "$HOME/.claude/accounts"
    chmod 700 "$HOME/.claude/accounts"
    echo '{"version": 1, "accounts": [], "activeAccountId": null}' > "$HOME/.claude/accounts/index.json"
fi
```

### 2. 플러그인 설치 상태 확인

```bash
echo "=== 2. 플러그인 설치 상태 ==="

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
            print(f'   경로: {path}')
else:
    print('WARN: account 플러그인 미등록')
"
else
    echo "WARN: installed_plugins.json 없음"
fi
```

### 3. 플러그인 파일 무결성

```bash
echo "=== 3. 파일 무결성 ==="

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
    echo "FAIL: 플러그인 설치 경로를 찾을 수 없음"
    echo "→ install.sh를 다시 실행하세요"
else
    MISSING=0
    for f in account_manager.py .claude-plugin/plugin.json hooks/hooks.json hooks-handlers/session-start.sh; do
        if [ -f "$INSTALL_PATH/$f" ]; then
            echo "OK: $f"
        else
            echo "FAIL: $f 없음"
            MISSING=$((MISSING + 1))
        fi
    done

    if [ -d "$INSTALL_PATH/claude_account_manager" ]; then
        echo "OK: claude_account_manager/ 패키지"
    else
        echo "FAIL: claude_account_manager/ 패키지 없음 (치명적)"
        echo "→ install.sh를 다시 실행하세요"
        MISSING=$((MISSING + 1))
    fi

    if [ -d "$INSTALL_PATH/commands" ]; then
        CMD_COUNT=$(ls "$INSTALL_PATH/commands/"*.md 2>/dev/null | wc -l | tr -d ' ')
        echo "OK: commands/ ($CMD_COUNT개 명령)"
    else
        echo "WARN: commands/ 없음"
    fi

    if [ "$MISSING" -eq 0 ]; then
        echo "모든 파일 정상!"
    else
        echo "${MISSING}개 파일 누락 → install.sh 재실행 필요"
    fi
fi
```

### 4. Keychain 토큰 확인

```bash
echo "=== 4. Keychain 토큰 ==="
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
            print(f'OK: 토큰 유효 ({hours}h {mins}m 남음)')
        else:
            print('WARN: 토큰 만료됨 (재로그인 필요)')
    if oauth.get('refreshToken'):
        print('OK: Refresh 토큰 존재')
    else:
        print('FAIL: Refresh 토큰 없음 (재로그인 필요)')
else:
    print('FAIL: Keychain에 credential 없음 (로그인 필요)')
"
```

### 5. 중복 계정 확인

```bash
echo "=== 5. 중복 계정 ==="
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
    print(f'WARN: {len(duplicates)}개 중복 계정 발견')
    for dup, orig in duplicates:
        print(f'  중복: {dup[\"id\"]} ↔ {orig[\"id\"]} ({dup[\"email\"]})')
    print('→ /account:remove로 불필요한 계정을 삭제하세요')
else:
    print('OK: 중복 없음')
"
```

### 6. 결과 요약

모든 체크가 완료되면 결과를 요약하여 사용자에게 보여주세요:
- OK 항목 수
- WARN 항목과 권장 조치
- FAIL 항목과 즉시 조치 필요 사항
