---
name: account:remove
description: 저장된 계정 삭제. "계정 삭제", "계정 제거", "remove account" 요청 시 사용.
argument-hint: [계정ID]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Remove

$ARGUMENTS

## Instructions

1. 계정 목록 확인:
```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" list
```

2. 계정ID 미제공 시:
   - AskUserQuestion으로 삭제할 계정 선택 요청
   - "취소" 옵션 포함

3. 삭제 확인:
   - AskUserQuestion으로 "정말 삭제하시겠습니까?" 확인

4. 삭제 실행:
```bash
echo "y" | python3 "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/account_manager.py" remove <계정ID>
```

**중요**: 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.
