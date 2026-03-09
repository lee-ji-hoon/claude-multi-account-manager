# multi-login-claude - Project Instructions

## Project Overview
Claude Code 다중 계정 관리 플러그인. Python으로 작성되었으며 macOS Keychain을 사용합니다.

### Key Files
- `account_manager.py`: Entry point (얇은 래퍼)
- `claude_account_manager/`: 핵심 패키지
  - `config.py`: 상수, 경로, Plan 제한
  - `ui.py`: 색상, 포맷팅 유틸리티
  - `keychain.py`: macOS Keychain 연동
  - `storage.py`: 파일 I/O (index.json, claude.json)
  - `token.py`: OAuth 토큰 관리
  - `api.py`: Anthropic API 호출
  - `account.py`: 계정 비즈니스 로직
  - `commands/`: CLI 명령어 핸들러
- `hooks-handlers/`: Hook 스크립트
- `.claude-plugin/plugin.json`: 플러그인 메타데이터

### Release Rules (필수)

**릴리즈 시 반드시 `/account:release` 스킬을 사용할 것!**

릴리즈 프로세스:
1. `plugin.json` 버전 업데이트 (캐시된 모든 버전보다 높게)
2. develop 브랜치에 커밋 + 태그 생성
3. **main 브랜치로 머지** (필수!)
4. main + 태그 푸시
5. 마켓플레이스 캐시 업데이트 확인

```bash
# 캐시된 버전 확인 (새 버전은 이보다 높아야 함)
ls ~/.claude/plugins/cache/lee-ji-hoon/account/
```

### Data Locations
- 계정 정보: `~/.claude/accounts/index.json`
- OAuth 토큰: macOS Keychain
- 프로필: `~/.claude/accounts/profile_{id}.json`
- 자격증명: `~/.claude/accounts/credential_{id}.json`

### Commands
```bash
/account:list              # 계정 목록 + 사용량
/account:add [이름]        # 현재 계정 저장
/account:switch [id]       # 계정 전환
/account:remove [id]       # 계정 삭제
/account:set-plan [id] [plan]  # Plan 설정
/account:check             # 토큰 상태 확인
```

### Hooks
| Hook | 트리거 | 동작 |
|------|--------|------|
| SessionStart | 세션 시작 | 계정 등록 + 모든 토큰 갱신 |
| UserPromptSubmit | 메시지 입력 | 만료 임박(1시간 이내) 토큰 갱신 |

### OAuth Token Refresh
- 엔드포인트: `https://platform.claude.com/v1/oauth/token`
- Client ID: `9d1c250a-e61b-44d9-88ed-5944d1962f5e`
- 토큰 유효기간: 8시간 (28800초)
- Refresh Token: 일회성 (갱신 시 새 토큰 발급)

### Tech Stack
- Python 3 (표준 라이브러리만 사용)
- macOS Keychain (`security` CLI)
- Claude Code Plugin System

### Testing
- 터미널에서 직접 `python3 account_manager.py` 실행
- `/account:list`로 사용량 표시 확인
- `/account:check`로 토큰 상태 확인
