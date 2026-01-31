---
description: 계정의 Plan 설정
argument-hint: <계정ID> <Plan>
allowed-tools: [Bash]
---

# Account Set Plan

계정의 Plan을 변경합니다.

## Arguments

$ARGUMENTS

## Instructions

다음 명령을 실행하세요:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" set-plan $ARGUMENTS
```

## Valid Plans

- Free
- Pro
- Team
- Max5
- Max20
