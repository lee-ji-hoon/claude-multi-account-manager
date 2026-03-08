---
description: 텔레그램에서 계정 데이터 가져오기 (다른 맥에서 push한 것). "계정 가져오기", "pull", "동기화" 요청 시 사용.
argument-hint: [파일경로]
allowed-tools: [Bash]
---

# Account Pull

다른 맥에서 `/account:push`로 전송한 계정 데이터를 가져옵니다.

## Instructions

1. pull 명령을 실행하고 **결과를 사용자에게 그대로 출력**하세요:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" pull $ARGUMENTS
```

2. 가져오기 완료 후 `/account:list`로 확인을 안내하세요.

**중요**: 모든 명령 실행 후 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.

## Notes

- 인자 없이 실행: 텔레그램 고정 메시지에서 자동으로 가져옴
- 파일 경로 제공: 로컬 JSON 파일에서 가져옴
- 이미 등록된 계정은 자동으로 스킵됨
