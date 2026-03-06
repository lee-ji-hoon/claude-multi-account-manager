---
name: export
description: 현재 계정 정보 추출 (다른 컴으로 옮기기). "계정 내보내기", "export" 요청 시 사용.
allowed-tools: [Bash]
---

# Account Export

현재 로그인된 계정 정보를 JSON 형식으로 추출합니다.
다른 컴에서 `/account:import`로 가져올 수 있습니다.

## Instructions

1. 계정 정보를 추출하고 **결과를 사용자에게 그대로 출력**하세요:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/account_manager.py" export
```

2. 추출 완료 후 사용자에게 다음을 안내하세요:
   - 생성된 JSON은 안전한 방식으로 다른 컴에 전달
   - 다른 컴에서 `/account:import`로 가져오기 가능

**중요**: 모든 명령 실행 후 출력 결과를 코드 블록 없이 그대로 사용자에게 보여주세요.

## Notes

- 추출된 JSON에는 유효한 OAuth 토큰이 포함됩니다
- 신뢰할 수 있는 네트워크 경로를 사용하여 전달하세요
- macOS에서는 자동으로 클립보드에 복사됩니다
