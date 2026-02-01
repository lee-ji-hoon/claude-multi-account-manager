---
description: 등록된 계정 목록 및 사용량 표시
allowed-tools: [Bash]
---

# Account List

등록된 Claude 계정 목록과 실시간 사용량을 표시합니다.

## Instructions

다음 명령을 실행하세요:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" list
```

## Features

- 모든 등록된 계정 표시
- 현재 세션 / 주간 사용량 프로그레스 바
- 리셋까지 남은 시간
- 토큰 상태 (만료/유효)
