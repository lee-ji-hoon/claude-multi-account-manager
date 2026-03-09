---
name: account:add
description: 현재 로그인된 계정 저장. "계정 추가", "계정 저장", "add account" 요청 시 사용.
argument-hint: [이름]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Add

$ARGUMENTS

## Instructions

1. 계정 추가 실행:
```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" add $ARGUMENTS
```

2. "이미 등록된 계정입니다" 출력 시:
   - AskUserQuestion으로 사용자에게 옵션 제시:
     - "토큰만 갱신" - 현재 Keychain 토큰으로 업데이트
     - "새로 로그인 후 갱신" - /login 안내
     - "취소"
   - "토큰만 갱신" 선택 시:
     ```bash
     echo "1" | python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" add
     ```

**중요**: 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.
