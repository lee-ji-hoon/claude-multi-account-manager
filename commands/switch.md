---
description: 다른 계정으로 전환
argument-hint: [계정ID]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Switch

다른 Claude 계정으로 전환합니다.

## Arguments

$ARGUMENTS

## Instructions

1. 먼저 계정 목록을 확인합니다:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" list
```

2. 계정ID가 인자로 제공되지 않은 경우:
   - AskUserQuestion 도구를 사용하여 사용자에게 전환할 계정을 선택하도록 질문하세요
   - 선택지에 각 계정의 이름, Plan, 이메일을 표시하세요

3. 선택된 계정으로 전환 실행:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" switch <선택된_계정ID>
```

4. 전환 완료 후 사용자에게 Claude Code 재시작이 필요함을 안내하세요.

## Notes

- 전환 후 Claude Code를 재시작해야 변경사항이 적용됩니다
- OAuth 토큰이 자동으로 교체됩니다
