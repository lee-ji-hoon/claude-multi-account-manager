---
name: account:switch
description: 다른 계정으로 전환. "계정 전환", "계정 바꾸기", "switch account" 요청 시 사용.
argument-hint: [계정ID]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Switch

$ARGUMENTS

## Instructions

1. 계정 목록 확인:
```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" list
```

2. 계정ID 미제공 시:
   - AskUserQuestion으로 전환할 계정 선택 요청
   - 각 계정의 이름, Plan, 이메일 표시

3. 전환 실행:
```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" switch <계정ID>
```

4. 완료 후 Claude Code 재시작 필요 안내

**중요**: 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.
