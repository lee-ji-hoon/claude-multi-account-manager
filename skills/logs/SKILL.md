---
description: 토큰 갱신 로그 확인. "로그", "갱신 기록", "401 에러", "logs" 요청 시 사용.
argument-hint: [export|path]
allowed-tools: [Bash]
---

# Account Logs

토큰 갱신 로그를 조회합니다. 401 에러, 갱신 실패 등의 이력을 확인할 수 있습니다.

## Instructions

1. 기본 사용 (최근 50줄 출력):
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" logs
```

2. 인자가 "export"인 경우 (데스크탑으로 복사):
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" logs export
```

3. 인자가 "path"인 경우 (로그 파일 경로만 출력):
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" logs path
```

**중요**: 모든 명령 실행 후 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.

## Log Levels

- **ERROR** (빨강): 갱신 실패, 401 에러 등 심각한 문제
- **WARN** (노랑): 토큰 만료, expiresAt 누락 등 주의 필요
- **INFO** (회색): 정상 갱신, 토큰 상태 기록

## Notes

- 로그는 세션 시작 시 자동 기록됩니다
- 파일 위치: `~/.claude/accounts/logs/token-refresh.log`
- 최대 512KB, 초과 시 자동 회전
- `export`로 데스크탑에 복사 후 공유 가능
