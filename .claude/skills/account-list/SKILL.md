---
name: account:list
description: 등록된 계정 목록 및 사용량 표시. "계정 목록", "계정 보기", "list accounts" 요청 시 사용.
allowed-tools: [Bash]
---

# Account List

등록된 Claude 계정 목록과 실시간 사용량을 표시합니다.

## Instructions

다음 명령을 실행하고 **결과를 사용자에게 그대로 출력**하세요:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" list
```

**중요**: 명령 실행 후 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.
