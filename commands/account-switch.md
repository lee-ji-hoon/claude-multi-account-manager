---
description: 다른 계정으로 전환
argument-hint: [계정ID]
allowed-tools: [Bash]
---

# Account Switch

다른 Claude 계정으로 전환합니다.

## Arguments

$ARGUMENTS

## Instructions

다음 명령을 실행하세요:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" switch $ARGUMENTS
```

## Notes

- 계정ID를 생략하면 대화형 선택 UI가 표시됩니다
- 전환 후 Claude Code를 재시작해야 합니다
- OAuth 토큰이 자동으로 교체됩니다
