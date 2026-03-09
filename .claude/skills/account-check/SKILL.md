---
name: account:check
description: OAuth 토큰 상태 확인. "토큰 확인", "토큰 상태", "check token" 요청 시 사용.
allowed-tools: [Bash]
---

# Account Check

## Instructions

다음 명령을 실행하고 **결과를 사용자에게 그대로 출력**하세요:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" check
```

**중요**: 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.
