---
name: account:export
description: 현재 계정 정보 추출 (다른 컴으로 옮기기). "계정 내보내기", "export" 요청 시 사용.
allowed-tools: [Bash]
---

# Account Export

## Instructions

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" export
```

**중요**: 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.
