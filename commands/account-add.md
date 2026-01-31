---
description: 현재 로그인된 계정 저장
argument-hint: [이름]
allowed-tools: [Bash]
---

# Account Add

현재 로그인된 Claude 계정을 저장합니다.

## Arguments

$ARGUMENTS

## Instructions

다음 명령을 실행하세요:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" add $ARGUMENTS
```

## Notes

- Plan 선택 프롬프트가 표시됩니다 (Free/Pro/Team/Max5/Max20)
- OAuth 토큰이 macOS Keychain에서 저장됩니다
- 이름을 생략하면 displayName 또는 email에서 자동 생성됩니다
