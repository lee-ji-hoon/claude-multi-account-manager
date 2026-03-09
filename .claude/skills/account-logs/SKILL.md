---
name: account:logs
description: 토큰 갱신 로그 확인. "로그", "갱신 기록", "401 에러", "logs" 요청 시 사용.
argument-hint: [clear]
allowed-tools: [Bash]
---

# Account Logs

$ARGUMENTS

## Instructions

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" logs $ARGUMENTS
```

**중요**: 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.
