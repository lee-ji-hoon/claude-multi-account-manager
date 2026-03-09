---
name: account:set-plan
description: 계정의 Plan 수동 설정. "Plan 변경", "플랜 설정", "set plan" 요청 시 사용.
argument-hint: [계정ID] [Plan]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Set Plan

$ARGUMENTS

## Instructions

1. 계정 목록 확인:
```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" list
```

2. 계정ID 미제공 시: AskUserQuestion으로 선택

3. Plan 미제공 시: AskUserQuestion으로 선택 (Free, Pro, Team, Max5, Max20)

4. 설정 실행:
```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" set-plan <계정ID> <Plan>
```

**중요**: 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.
