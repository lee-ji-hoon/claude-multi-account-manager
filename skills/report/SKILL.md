---
description: 버그 리포트 GitHub Issue 생성. "버그 신고", "bug report", "이슈 등록", "report" 요청 시 사용.
allowed-tools: [Bash]
---

# Account Bug Report

문제 진단 정보를 수집하고 GitHub Issue를 자동 생성합니다.

## Instructions

### 1. 진단 정보 수집

아래 명령들을 실행하여 진단 정보를 수집하세요:

```bash
echo "=== 환경 정보 ==="
echo "OS: $(sw_vers -productVersion)"
echo "Python: $(python3 --version 2>&1)"
echo "Plugin: $(python3 -c "import json; print(json.load(open('${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo 'unknown')"
echo "Accounts: $(python3 -c "import json,os; print(len(json.load(open(os.path.expanduser('~/.claude/accounts/index.json'))).get('accounts',[])))" 2>/dev/null || echo '?')개"
```

```bash
echo "=== 최근 에러 로그 ==="
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" logs 2>&1 | grep -E "ERROR|WARN|FAIL" | tail -20
```

```bash
echo "=== 토큰 상태 ==="
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" check 2>&1
```

### 2. 사용자에게 증상 확인

AskUserQuestion으로 다음을 질문하세요:
- **어떤 문제가 발생했나요?** (증상 설명)
- **재현 방법이 있나요?** (있다면)

### 3. GitHub Issue 생성

수집된 정보와 사용자 설명을 조합하여 Issue를 생성하세요:

```bash
gh issue create --repo lee-ji-hoon/claude-multi-account-manager \
  --title "[Bug] {증상 요약}" \
  --body "$(cat <<'ISSUE_EOF'
## 증상
{사용자가 설명한 증상}

## 재현 방법
{재현 방법 또는 "확인되지 않음"}

## 진단 정보
- OS: {버전}
- Plugin: v{버전}
- 계정 수: {N}개

### 에러 로그
```
{에러 로그 발췌}
```

### 토큰 상태
```
{토큰 상태 출력}
```

---
> 🤖 `/account:report`로 자동 생성됨
ISSUE_EOF
)" --label bug
```

### 4. 결과 안내

Issue URL을 사용자에게 보여주세요.

## Notes

- `gh` CLI가 인증되어 있어야 합니다
- Issue에 민감 정보(토큰, 비밀번호)는 포함하지 마세요
- 에러 로그에서 accessToken, refreshToken 등은 자동으로 마스킹하세요
