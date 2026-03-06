---
name: import
description: 다른 컴의 계정 가져오기. "계정 가져오기", "import" 요청 시 사용.
argument-hint: [JSON 또는 파일경로]
disable-model-invocation: true
allowed-tools: [Bash, AskUserQuestion]
---

# Account Import

다른 컴퓨터의 계정 정보를 현재 Claude Code에 가져옵니다.

## Instructions

1. 인자가 제공된 경우 (JSON 문자열 또는 파일 경로):
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" import $ARGUMENTS
```

2. 인자가 없는 경우:
   - AskUserQuestion으로 JSON 입력 방식을 질문하세요:
     - "통합 JSON 붙여넣기" - `/account:export`한 JSON을 직접 입력
     - "파일 경로 지정" - JSON 파일 경로 입력
   - 입력받은 데이터로 import 실행

3. 실행 결과를 **사용자에게 그대로 출력**하세요.

**중요**: 모든 명령 실행 후 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.

## Supported Formats

### 표준 형식 (권장)
```json
{
  "profile": { "emailAddress": "...", ... },
  "credential": { "access_token": "...", ... }
}
```

### claude_auth.json 형식
```json
{
  "oauthAccount": { "emailAddress": "...", ... },
  ...
}
```

## Notes

- 동일 이메일이라도 다른 Team/Organization이면 별도로 등록 가능
- 기존 계정과 중복되면 안내 메시지 표시
