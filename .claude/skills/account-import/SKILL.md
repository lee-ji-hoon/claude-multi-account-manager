---
name: account:import
description: 다른 컴의 계정 가져오기. "계정 가져오기", "import" 요청 시 사용.
argument-hint: [JSON 데이터]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Import

$ARGUMENTS

## Instructions

1. JSON 데이터 미제공 시:
   - AskUserQuestion으로 export 명령 출력물을 붙여넣도록 안내

2. Import 실행:
```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" import '$ARGUMENTS'
```

**중요**: 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.
