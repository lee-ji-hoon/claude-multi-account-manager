---
description: 계정의 Plan 설정
argument-hint: [계정ID] [Plan]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Set Plan

계정의 Plan을 수동으로 변경합니다.

## Arguments

$ARGUMENTS

## Instructions

1. 먼저 계정 목록을 확인하고 **결과를 사용자에게 그대로 출력**하세요:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" list
```

2. 계정ID가 인자로 제공되지 않은 경우:
   - AskUserQuestion 도구를 사용하여 사용자에게 계정을 선택하도록 질문하세요

3. Plan이 인자로 제공되지 않은 경우:
   - AskUserQuestion 도구를 사용하여 Plan을 선택하도록 질문하세요
   - 선택지: Free, Pro, Team, Max5, Max20

4. Plan 설정 실행하고 **결과를 사용자에게 그대로 출력**하세요:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" set-plan <계정ID> <Plan>
```

**중요**: 모든 명령 실행 후 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.

## Valid Plans

- Free
- Pro
- Team
- Max5 (Claude Max 5 프로젝트)
- Max20 (Claude Max 20 프로젝트)

## Notes

- 일반적으로 Plan은 자동 감지됩니다
- 자동 감지가 잘못된 경우에만 수동 설정하세요
