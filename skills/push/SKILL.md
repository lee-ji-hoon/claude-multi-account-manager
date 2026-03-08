---
description: 계정 데이터를 텔레그램으로 전송 (다른 맥 동기화). "계정 동기화", "push", "다른 맥으로" 요청 시 사용.
allowed-tools: [Bash]
---

# Account Push

등록된 모든 계정 데이터를 텔레그램으로 전송합니다.
다른 맥에서 `/account:pull`로 가져올 수 있습니다.

## Instructions

1. push 명령을 실행하고 **결과를 사용자에게 그대로 출력**하세요:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" push
```

2. 성공 시 다른 맥에서 `/account:pull`로 가져올 수 있음을 안내하세요.

**중요**: 모든 명령 실행 후 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.

## Notes

- 텔레그램 설정 필요: `~/.claude/hooks/telegram-config.json` (bot_token, chat_id)
- 전송된 데이터는 텔레그램 채팅에 고정 메시지로 저장됨
- OAuth 토큰 포함 - 토큰은 8시간 후 만료되므로 빠르게 pull 권장
