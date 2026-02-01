---
description: 현재 로그인된 계정 저장
argument-hint: [이름]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Add

현재 로그인된 Claude 계정을 저장합니다.

## Arguments

$ARGUMENTS

## Instructions

1. 먼저 계정 추가를 시도합니다:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" add $ARGUMENTS
```

2. 만약 "이미 등록된 계정입니다" 메시지가 출력되면:
   - AskUserQuestion 도구를 사용하여 사용자에게 다음 옵션을 제시하세요:
     - "토큰만 갱신" - 현재 Keychain의 토큰으로 업데이트
     - "새로 로그인 후 갱신" - /login 안내
     - "취소"

3. 선택에 따라 실행:
   - "토큰만 갱신" 선택 시:
     ```bash
     echo "1" | python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" add
     ```
   - "새로 로그인" 선택 시: 사용자에게 /login 후 다시 /account-add 실행 안내

## Notes

- Plan은 credential에서 자동 감지됩니다 (rateLimitTier, subscriptionType)
- 이름을 생략하면 displayName 또는 email에서 자동 생성됩니다
- OAuth 토큰이 macOS Keychain에 저장됩니다
