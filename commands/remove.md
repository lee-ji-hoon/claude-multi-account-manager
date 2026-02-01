---
description: 저장된 계정 삭제
argument-hint: [계정ID]
allowed-tools: [Bash, AskUserQuestion]
---

# Account Remove

저장된 계정을 삭제합니다.

## Arguments

$ARGUMENTS

## Instructions

1. 먼저 계정 목록을 확인합니다:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" list
```

2. 계정ID가 인자로 제공되지 않은 경우:
   - AskUserQuestion 도구를 사용하여 사용자에게 삭제할 계정을 선택하도록 질문하세요
   - 선택지에 각 계정의 이름, Plan, 이메일을 표시하세요
   - "취소" 옵션도 포함하세요

3. 삭제 확인:
   - AskUserQuestion으로 "정말 삭제하시겠습니까?" 확인 질문을 하세요
   - 계정 이름과 이메일을 표시하세요

4. 확인된 경우 삭제 실행:
```bash
echo "y" | python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" remove <선택된_계정ID>
```

## Notes

- 삭제된 계정은 복구할 수 없습니다
- 프로필 파일과 credential 파일이 함께 삭제됩니다
