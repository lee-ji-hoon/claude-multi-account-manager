# Changelog

All notable changes to this project will be documented in this file.

## [2.5.2] - 2026-07-08

### Fixed
- **credential 교차 오염 수정** — switch나 `/login` 직후 `~/.claude.json`(oauthAccount)과 Keychain이 잠깐 어긋나는 desync 윈도우에, hook이 Keychain의 새 계정 토큰을 이전 계정 슬롯에 저장하던 문제 (2026-07-08 실사고: gmail 토큰이 soop 슬롯에 저장되어 두 계정이 동일 사용량으로 표시됨)
  - `owner.py` 신설: `/api/oauth/profile`로 토큰 실소유 계정(uuid/email/org)을 확인, 토큰 해시 키로 캐시 (신규 토큰당 API 1회)
  - Keychain credential을 슬롯 파일에 쓰는 5개 경로 전부에 소유자 검증 가드 추가: `cmd_refresh_all`(현재 계정 저장), `cmd_refresh_expiring`(Keychain→파일 동기화), `_auto_migrate`(credential 복구), `cmd_add`(토큰만 갱신 + 신규 저장), `cmd_auto_add`
  - 소유자 불일치 또는 확인 불가 시 저장을 스킵하고 로그/메시지 출력 (fail-closed — 다음 hook에서 자동 재시도)
  - 동일 이메일이 여러 org에 속한 경우 org uuid까지 비교하여 org 단위 슬롯 구분 유지
- **Max20 계정이 `Max5`로 표시되던 문제** — `_fetch_usage_from_api`의 planName 계산이 `subscriptionType: "max"`(숫자 없음)일 때 rateLimitTier를 무시하고 무조건 Max5로 표기. `detect_plan_from_credential`과 동일하게 rateLimitTier로 세분화
- **계정 삭제 감사 로그 부재** — `account remove`가 실행돼도 누가/언제/어떤 상태의 계정을 지웠는지 기록이 없어 사후 추적이 불가능했음 (2026-07-08: `dlwlgns1240_soop` 계정 항목이 원인 불명으로 두 차례 삭제됨). 삭제 확정 직후 계정 식별자·이메일·조직·credential 실존 여부·actor 컨텍스트(대화형 여부, 부모 프로세스 id, 세션 id)를 `token-refresh.log`에 WARN으로 기록 (Claude/Codex 삭제 경로 모두)

### Added
- `tests/test_owner_guard.py` — 소유자 검증 단위 테스트 + 교차 오염 시나리오 회귀 테스트 (오프라인, 전부 mock)
- `tests/test_remove_audit.py` — 계정 삭제 감사 로깅 회귀 테스트 (반쪽 상태 삭제 시나리오 포함)
- cc-fleet single-owner refresh (`_cc_fleet_accounts`) — 이전 릴리즈 이후 설치 캐시에만 존재하던 핫패치를 git 이력에 포팅 (컨테이너가 refresh owner로 lease 중인 계정은 mac 쪽 자동 토큰 회전을 skip해 회전 충돌 방지)

## [2.5.1] - 2026-05-13

### Removed
- **v2.5.0의 Long-lived OAuth token 지원 전면 revert** — `claude setup-token`이 발급하는 토큰은 `user:inference` scope만 가지고 `user:sessions:claude_code` scope가 없어 **인터랙티브 Claude Code 세션을 시작할 수 없음** (Anthropic 정책상 제한). 등록·switch는 가능하지만 활성화 시 "Not logged in" 표시되어 실용성 없음.
- 제거된 항목:
  - `/account:add`의 Long-lived 분기, `cmd_add_long_lived` 함수
  - `/account:export-token` 명령
  - `/account:switch --shell-export` 플래그, `build_shell_export_lines` 함수
  - `list` / `switch` UI의 `[CI]` 배지 + D-day 표시
  - SessionStart hook의 long-lived 만료 임박 경고
  - `refresh-all` / `refresh-expiring` / `check`의 long-lived skip 분기
  - zsh wrapper v4 → v2 (Codex 시점 기본)
  - `claude_account_manager/long_lived.py`, `commands/export_token_cmd.py`, 관련 테스트 5개

### Note
CI/스크립트 환경에서 `claude -p "..."` 같은 비인터랙티브 호출이 필요하면 그대로 `CLAUDE_CODE_OAUTH_TOKEN` 환경변수를 export하여 사용 가능 (이 플러그인 외부에서 직접 관리).

## [2.5.0] - 2026-05-13

### Added
- **Long-lived OAuth token 지원** — `claude setup-token`이 발급하는 1년 유효 토큰을 일반 계정과 동일하게 등록·전환·관리
  - `/account:add` 진입 시 `[2] Long-lived 토큰 등록` 선택지 추가
  - `/account:export-token <id>` 명령 신설 — `export CLAUDE_CODE_OAUTH_TOKEN='...'` stdout 출력
  - `/account:switch --shell-export` 플래그 — long-lived 활성화 시 env 라인 자동 emit, 일반 OAuth로 복귀 시 `unset` 라인 emit
  - `list` / `switch` UI에 `[CI]` 배지 + D-day 만료 표시 (inference-only scope라 usage API skip)
  - SessionStart hook이 D-7 이내 만료 임박 long-lived 토큰 stderr 경고
  - `refresh-all` / `refresh-expiring` / `check`가 `tokenType=="long-lived"` 계정 자동 skip
- zsh wrapper v4 — `account switch <id>` 와 `account-switch <id>` 둘 다 `CLAUDE_CODE_OAUTH_TOKEN` env 자동 동기화 (분기 로직을 `_account_mgr_run` 한 곳으로 통합)

### Fixed
- `switch --shell-export`가 동일 계정 재선택 시에도 env 라인 출력 (새 셸 첫 활성화 시 env 동기화 보장)
- `switch` 대화형 선택 UI가 long-lived 토큰으로 `/api/oauth/usage` 호출하여 INVALID 표시되던 회귀

### Documentation
- README.md / README.ko.md에 "Long-lived OAuth Token (CI/Scripts)" 섹션 추가
- `docs/superpowers/specs/` 및 `docs/superpowers/plans/` 에 설계·구현 문서 보관
- `scripts/poc_long_lived.sh` POC 검증 스크립트

## [0.1.0] - 2026-02-01

### What's changed

**Added**
- UserPromptSubmit hook으로 만료 임박(1시간 이내) 토큰 자동 갱신
- 세션 중간에 토큰 만료 방지 기능

**Fixed**
- README Mermaid 다이어그램 렌더링 오류 수정

**Improved**
- Claude 세션 내 설치 방법 안내 추가
- CLAUDE.md에 OAuth 상세 정보 추가

### Commits

```
03676cf fix: Mermaid syntax error and add session install guide
```

### Full Changelog

https://github.com/lee-ji-hoon/claude-multi-account-manager/compare/v0.0.1...v0.1.0

---

## [0.0.1] - 2026-02-01

### What's changed

**Added**
- Initial release of Claude Code multi-account manager plugin
- Multiple account management without logout (`/account:add`, `/account:switch`, `/account:remove`)
- Real-time usage monitoring with visual progress bars
- Automatic token refresh for all accounts on session start
- Plan auto-detection (Free / Pro / Team / Max5 / Max20)
- SessionStart hook for automatic account registration
- macOS Keychain integration for secure token storage

**Technical Details**
- OAuth token refresh via `platform.claude.com/v1/oauth/token`
- Refresh token rotation (single-use tokens)
- Token validity: 8 hours (28800 seconds)

### Commits

```
b360843 feat: Initial release - Claude Code multi-account manager plugin
deef16d fix: Correct SessionStart hook configuration format
6121cff docs: Update installation to plugin-based approach
eb40c43 docs: Add marketplace installation method
404c682 refactor: Simplify command structure and add marketplace support
03c0a04 feat: Always refresh all account tokens on session start
efad03b fix: Use correct OAuth endpoint for token refresh
e8dd30c docs: Add architecture documentation with diagrams
092bb67 docs: Add both dialog and terminal installation methods
2c4c8a4 docs: Update README with new command structure
b96b08b docs: Simplify README with Mermaid diagram
```

### Full Changelog

https://github.com/lee-ji-hoon/claude-multi-account-manager/commits/main
