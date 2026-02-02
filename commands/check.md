---
description: OAuth 토큰 상태 확인
allowed-tools: [Bash]
---

# Account Check

현재 OAuth 토큰의 상태를 확인합니다.

## Instructions

다음 명령을 실행하고 **결과를 사용자에게 그대로 출력**하세요:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" check
```

**중요**: 명령 실행 후 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.

## Features

- 토큰 유효성 확인
- 만료 시 자동 갱신 시도
- 현재/주간 사용량 표시
- 만료된 경우 재로그인 방법 안내
