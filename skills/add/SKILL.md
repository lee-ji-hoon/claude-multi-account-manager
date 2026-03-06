---
description: 현재 로그인된 계정 저장. "계정 추가", "계정 저장", "add account" 요청 시 사용.
argument-hint: [이름]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Add

현재 로그인된 Claude 계정을 저장합니다.

## Instructions

1. 계정 추가를 실행하고 **결과를 사용자에게 그대로 출력**하세요:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" add $ARGUMENTS
```

2. "이미 등록된 계정입니다" 메시지가 출력되면:
   - AskUserQuestion으로 다음 옵션을 제시하세요:
     - "토큰만 갱신" - 현재 Keychain의 토큰으로 업데이트
     - "새로 로그인 후 갱신" - /login 안내
     - "취소"

3. 선택에 따라 실행하고 **결과를 사용자에게 그대로 출력**하세요:
   - "토큰만 갱신" 선택 시:
     ```bash
     echo "1" | python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" add
     ```
   - "새로 로그인" 선택 시: /login 후 다시 실행 안내

**중요**: 모든 명령 실행 후 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.

## Notes

- Plan은 credential에서 자동 감지됩니다 (rateLimitTier, subscriptionType)
- 이름을 생략하면 displayName 또는 email에서 자동 생성됩니다
- 동일 이메일이라도 다른 Team/Organization이면 별도 계정으로 등록됩니다
