# Long-lived OAuth Token 지원 설계

- 일자: 2026-05-13
- 대상: claude-multi-account-manager
- 상태: design (브레인스토밍 완료, 구현 plan 작성 직전)

## 1. 목적

`claude setup-token`으로 발급되는 1년 유효 OAuth 토큰(이하 *long-lived 토큰*)을
multi-account-manager에 일반 OAuth 계정과 **동등하게** 등록·관리·전환할 수 있도록 한다.

- 등록: `/account:add` 인터랙티브 분기에서 long-lived 등록 지원
- 활성화: `switch` 한 번으로 keychain wrap + 환경변수 export 둘 다 처리 (Hybrid)
- 노출: `list`에서 일반 계정과 같은 표에 표시 + 만료 D-day
- 이력: SessionStart hook이 long-lived는 refresh 시도하지 않음 + 임박 만료 경고

## 2. 배경

### 2.1 일반 OAuth vs long-lived 토큰

| 항목 | 일반 OAuth | long-lived (`claude setup-token`) |
|---|---|---|
| 유효기간 | 8시간 | 365일 |
| Refresh token | 있음 (1회용 갱신) | **없음** |
| 사용 경로 | macOS Keychain (`claudeAiOauth.accessToken`) | `CLAUDE_CODE_OAUTH_TOKEN` 환경변수 |
| Scope | 인터랙티브 전체 (Remote Control 포함) | inference only |
| 발급 | 브라우저 OAuth flow → keychain 자동 저장 | `claude setup-token` → stdout 출력 (저장 안 됨) |

### 2.2 기존 코드 자산

- `claude_account_manager/keychain.py`: keychain read/write 추상화
- `claude_account_manager/token.py`: refresh 로직 + `check_token_status`
- `claude_account_manager/account.py`: id 생성, plan 감지, 중복 체크
- `commands/{add,switch,list,token}_cmd.py`: 명령 핸들러
- SessionStart hook: 자동 refresh
- `.zshrc` function-based alias (`a7bf349`): function 안에서 eval 처리 가능

## 3. 결정사항 요약

| 결정 | 선택지 | 결정 |
|---|---|---|
| 시나리오 | A: CI 보관소만 / B: 일반 계정처럼 통합 / C: 모두 | **C — 등록 + 활성화 + export 모두 지원** |
| 활성화 방식 | A: keychain wrap / B: 환경변수만 / C: Hybrid | **C — keychain wrap + export 라인 둘 다 제공** |
| 등록 UX | A: 새 명령 / B: 기존 `/account:add` 분기 / C: setup-token wrapping | **B — `/account:add`에서 유형 선택** |
| env 충돌 대응 | A: 경고만 / B: function wrapper eval / C: shell rc 자동 수정 | **B — function wrapper가 eval 처리** |

## 4. 데이터 모델

### 4.1 `credential_{id}.json` (기존 schema 재사용)

```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...(1년 토큰)",
    "refreshToken": "",
    "expiresAt": 1779302400000,
    "subscriptionType": "max",
    "rateLimitTier": "default_claude_max_20x"
  }
}
```

규칙:
- `refreshToken`은 빈 문자열 (`null` 대신 — 기존 코드의 None-check 충돌 회피)
- `expiresAt`은 등록 시점 + 365일 (밀리초 epoch)
- `subscriptionType`/`rateLimitTier`는 사용자 입력 Plan으로부터 매핑

### 4.2 `index.json` 엔트리 확장

```json
{
  "id": "joel_token",
  "name": "joel-ci",
  "email": "joel@sooplive.com",
  "plan": "Max20",
  "tokenType": "long-lived",
  "tokenIssuedAt": "2026-05-13T10:00:00",
  "profileFile": "profile_joel_token.json",
  "credentialFile": "credential_joel_token.json",
  "createdAt": "2026-05-13T10:00:00"
}
```

규칙:
- `tokenType` 부재 = `"oauth"` (backward compatibility). 코드는 `acc.get("tokenType", "oauth")` 패턴.
- `tokenIssuedAt`은 D-day 계산용 (`expiresAt - 365일`로 역산 가능하지만 명시 저장이 안전)
- `profile_{id}.json`은 long-lived도 동일하게 생성하되 내용은 사용자가 입력한 email/displayName만 포함 (oauth account info 없음)

### 4.3 ID 생성 규칙

- 기본: `generate_account_id(email)` 기존 로직 재사용
- 일반 OAuth 계정과 충돌 시 `_token` suffix 추가 (예: `joel` → `joel_token`)
- long-lived 끼리 충돌 시 `_token_2`, `_token_3` ...
- account.py에 `generate_long_lived_account_id(email)` 헬퍼 추가

## 5. 명령 흐름

### 5.1 `/account:add` (분기 추가)

```
$ /account:add
  유형 선택
  ─────────────────────────
  [1] 현재 로그인된 OAuth 계정 저장 (기본)
  [2] Long-lived 토큰 등록 (CI/스크립트용, 1년 유효)
  ─────────────────────────
  번호 입력 (기본: 1): 2

  토큰 발급:
    터미널에서 'claude setup-token' 실행 → OAuth 후 출력되는 토큰 복사
  토큰 paste (입력 숨김): ****
  계정 이름: joel-ci
  이메일: joel@sooplive.com
  Plan 선택 [1=Free 2=Pro 3=Team 4=Max5 5=Max20]: 5

  검증 중...
  ✓ 토큰 포맷 OK
  ✓ Anthropic API 응답 200 (또는 403 inference-only도 OK로 간주)

  등록 완료
  ─────────────────────────
  ID: joel_token
  이름: joel-ci
  Plan: Max20
  Type: Long-lived
  만료: 2027-05-13 (D-365)
```

- 토큰 입력은 `getpass.getpass()` 사용 (echo off)
- 검증 단계는 옵션 (네트워크 오류 시 건너뛰기 가능)

### 5.2 `/account:switch <id>` (tokenType 분기)

**일반 OAuth 계정 → switch**
1. keychain `claudeAiOauth` 덮어쓰기
2. `--shell-export` 플래그가 있으면 stdout에 `unset CLAUDE_CODE_OAUTH_TOKEN` 출력

**Long-lived 계정 → switch**
1. credential을 wrap된 형태 그대로 keychain에 덮어쓰기
2. `--shell-export` 플래그가 있으면 stdout에 `export CLAUDE_CODE_OAUTH_TOKEN=<토큰>` 출력
3. 화면 안내: `Long-lived 토큰 활성화 (만료 D-day: 7일 후)`

### 5.3 `/account:export-token <id>` (신규 명령)

- 해당 계정의 토큰을 `export CLAUDE_CODE_OAUTH_TOKEN=<토큰>` 형태로 stdout 출력
- 일반 OAuth 계정도 가능 (현재 access token으로)
- long-lived/일반 동일하게 동작하지만 stderr에 만료 경고만 다르게 표시

### 5.4 `/account:list` (표시 컬럼 추가)

```
ID                 이름         Plan   Type        만료/사용량
─────────────────────────────────────────────────────────────────
* joel             joel         Max20  OAuth       7시간 후 (사용 12%)
  joel_token       joel-ci      Max20  Long-lived  D-364
  acme_token       acme-ci      Pro    Long-lived  D-23  ← yellow
  staging_token    staging      Pro    Long-lived  D-2   ← red
```

- `Type` 컬럼 신규
- long-lived는 usage API 호출 skip (성능 + 403 회피)
- 만료 표시: 일반은 시간 단위, long-lived는 D-day
- 색상: D-30 이내 yellow, D-7 이내 red, 만료 red strikethrough

### 5.5 `/account:check` (long-lived 분기)

- `tokenType == "long-lived"`인 계정 대상:
  - refresh 시도 안 함
  - `/api/oauth/usage` 호출 안 함
  - `expiresAt`만 비교 → `valid` / `expired` 판정
- 일반 OAuth는 기존 로직 그대로

### 5.6 SessionStart hook (long-lived skip + 만료 경고)

- 자동 refresh loop:
  ```python
  for acc in index["accounts"]:
      if acc.get("tokenType") == "long-lived":
          continue  # refresh 시도 안 함
      ...
  ```
- 만료 경고: long-lived 계정 중 D-7 이하인 항목 발견 시 stderr 출력
  ```
  [warning] long-lived 토큰 'joel-ci' 만료 D-3.
            갱신: claude setup-token → /account:add (다시 등록)
  ```

### 5.7 Shell function wrapper

- 기존 `.zshrc` 마커 블록 안에 `account:switch` function 정의
- 내부 동작:
  ```zsh
  account:switch() {
      local raw
      raw=$(python3 -m claude_account_manager switch --shell-export "$@" 2>&1)
      local rc=$?
      eval "$(echo "$raw" | grep -E '^(export|unset) ')"
      echo "$raw" | grep -vE '^(export|unset) '
      return $rc
  }
  ```
- `account:export-token`도 동일 패턴 (function 내부 eval)
- 사용자 UX: `account:switch joel_token` 한 줄 → 자동으로 env까지 적용

## 6. 에러 처리 매트릭스

### 6.1 등록 단계

| 케이스 | 처리 |
|---|---|
| 토큰 포맷 검증 실패 (`sk-ant-oat01-` prefix 아님) | 등록 거부 + 재입력 prompt |
| Anthropic API ping 403 | "inference-only scope. 토큰 유효한 것으로 가정하고 등록" 안내 후 진행 |
| Anthropic API ping 401 | "토큰 만료/무효. 다시 발급하세요" — 등록 거부 |
| 네트워크 오류 | 경고만 출력하고 등록 진행 (오프라인 등록 케이스) |
| 동일 토큰 이미 등록됨 | 중복 경고 + 기존 entry id 안내 |

### 6.2 활성화 단계

| 케이스 | 처리 |
|---|---|
| switch 후 Claude Code가 keychain의 long-lived 토큰을 거부 | `/account:check`가 long-lived에서 401 만나면 "keychain wrap이 거부됨. `eval $(account:export-token <id>)`로 환경변수 export 시도" 안내 |
| `CLAUDE_CODE_OAUTH_TOKEN` env가 set돼있는 상태에서 일반 OAuth로 switch | `--shell-export` stdout에 `unset CLAUDE_CODE_OAUTH_TOKEN` 포함 |

### 6.3 만료 경고

- 30일 이내 (D-30): yellow 표시
- 7일 이내 (D-7): red 표시 + SessionStart stderr 경고
- 만료: red strikethrough + `check`에서 `expired` 반환

### 6.4 보안

| 항목 | 처리 |
|---|---|
| 토큰 paste | `getpass.getpass()` (echo off) |
| credential 파일 권한 | 기존과 동일 0o600 |
| `--shell-export` stdout | 토큰이 stdout에 노출 → shell history 잔존 가능. README에 "wrapper function 경로 사용 권장" 명시 |
| keychain 저장 | 기존 `security` CLI mechanism 그대로 (process list 노출은 기존과 동일한 한계) |

## 7. 구현 단위

### 7.1 신규 파일

1. **`claude_account_manager/long_lived.py`**
   - `wrap_long_lived_token(token, plan) -> dict`
   - `is_long_lived_account(account_entry) -> bool`
   - `validate_token_format(token) -> bool`
   - `verify_token_with_api(token) -> tuple[bool, str]`
   - `format_expiry_dday(expires_at_ms) -> tuple[str, str]` (라벨, color hint)
   - `plan_to_subscription_type(plan) -> tuple[str, str]` (plan → subscriptionType, rateLimitTier)
2. **`claude_account_manager/commands/export_token_cmd.py`**
   - `cmd_export_token(id)` — stdout에 export 라인 출력
3. **`tests/test_long_lived.py`**
   - 단위 테스트 (아래 7.4 참조)

### 7.2 수정 파일

| 파일 | 변경 요지 |
|---|---|
| `commands/add_cmd.py` | `cmd_add()` 진입에 유형 선택 prompt, `cmd_add_long_lived()` 분기 함수 신설 |
| `commands/switch_cmd.py` | `shell_export` 인자, tokenType 분기, 만료 D-day 표시 |
| `commands/list_cmd.py` | Type 컬럼, long-lived는 usage 조회 skip, D-day 색상 |
| `commands/token_cmd.py` | `cmd_check`에 long-lived 분기 |
| `token.py` | 변경 없음 (caller에서 분기) |
| `account.py` | `generate_long_lived_account_id(email)` 헬퍼 추가 |
| `__main__.py` | `export-token` 서브커맨드, `switch --shell-export` 옵션 |
| `hooks-handlers/session-start.sh` + 자동 refresh 호출 경로 (구현 단계에서 grep으로 확인) | refresh loop에서 long-lived skip + 만료 경고 |
| `.zshrc` 마커 블록 코드 (`hooks-handlers/session-start.sh` 내부의 `write_v2_block`) | `account:switch`, `account:export-token` function wrapper |

### 7.3 SKILL.md

| 파일 | 변경 |
|---|---|
| `skills/account-add/SKILL.md` | 본문에 long-lived 분기 한 줄 추가 |
| `skills/account-switch/SKILL.md` | function wrapper 안내 추가 |
| `skills/account-list/SKILL.md` | Type/D-day 컬럼 추가 |
| `skills/account-export-token/SKILL.md` | **신규** |
| `README.md`, `README.ko.md` | long-lived 등록·export·function wrapper 사용법 섹션 추가 |

### 7.4 테스트 단위

- `test_wrap_long_lived_token`: schema 일관성 (필수 필드 모두 존재)
- `test_validate_token_format`: prefix 검증 (positive/negative)
- `test_token_type_dispatch_switch`: oauth/long-lived 각각 keychain 동작 확인 (mock keychain)
- `test_expiry_dday`: 경계값 (D-0, D-1, D-7, D-30, D-365)
- `test_id_collision`: `joel` + `joel_token` suffix 규칙
- `test_refresh_hook_skips_long_lived`: hook의 loop가 long-lived 항목 skip 확인
- `test_shell_export_format`: export/unset 라인이 zsh-eval 가능한 syntax

## 8. POC (구현 전 검증 필수)

다음 4개 가정은 미확인이므로 구현 전 5분 POC로 검증한다.

### 8.1 검증 대상

| ID | 가정 | 영향도 |
|---|---|---|
| A1 | long-lived 토큰을 `claudeAiOauth.accessToken`에 wrap하면 Claude Code가 그대로 사용한다 | 높음 |
| A2 | long-lived 토큰이 `/api/oauth/usage`에 403 응답한다 (inference-only scope) | 중간 |
| A3 | 토큰 포맷이 `sk-ant-oat01-` prefix 또는 유사한 안정된 prefix를 가진다 | 낮음 |
| A4 | keychain의 long-lived 토큰을 Claude Code가 refresh 시도하지 않는다 (expiresAt이 미래일 때) | 높음 |

### 8.2 POC 절차

```bash
# 1. 토큰 발급 (사용자 인터랙티브)
claude setup-token

# 2. usage API 검증 (A2, A3)
curl -i -H "Authorization: Bearer <TOKEN>" \
        -H "anthropic-beta: oauth-2025-04-20" \
        https://api.anthropic.com/api/oauth/usage

# 3. wrap → keychain 주입 → claude 기동 (A1, A4)
EXPIRES_MS=$(python3 -c "from datetime import datetime, timedelta; print(int((datetime.now()+timedelta(days=365)).timestamp()*1000))")
WRAPPED=$(jq -n --arg t "<TOKEN>" --argjson e $EXPIRES_MS '{claudeAiOauth:{accessToken:$t,refreshToken:"",expiresAt:$e,subscriptionType:"max",rateLimitTier:"default_claude_max_20x"}}')
security delete-generic-password -s "Claude Code-credentials" -a "$USER" 2>/dev/null
security add-generic-password -s "Claude Code-credentials" -a "$USER" -w "$WRAPPED"
claude --print "hello"  # 정상 응답이면 A1 통과
```

### 8.3 POC 결과 분기

| 결과 | 다음 단계 |
|---|---|
| A1 통과 + A4 통과 | 본 설계대로 진행 |
| A1 실패 | keychain wrap 폐기, switch는 export 안내만. 데이터 모델은 그대로. |
| A2 다른 응답 (200) | list/check에서 usage 표시 가능 — 단순화 |
| A4 실패 (refresh 시도됨) | expiresAt을 더 미래로 (10년 등) 시도 또는 keychain wrap 폐기 |

## 9. 단계적 출시

### Phase 1 — MVP (필수)
- `/account:add` 분기 + `/account:export-token` 신규 + `/account:list` Type 컬럼
- switch는 keychain wrap **시도**하되, 안 되더라도 export 안내로 fallback
- function wrapper 한 줄 추가

### Phase 2 — switch 완전 통합
- `--shell-export` 플래그 + function wrapper에서 자동 eval
- SessionStart hook의 long-lived skip

### Phase 3 — 만료 경고 + 폴리시
- D-day 색상, SessionStart 7일 경고, README 업데이트

각 phase는 독립 배포 가능. POC 결과에 따라 Phase 2 일부가 축소될 수 있음.

## 10. 롤백

- `tokenType` 필드는 backward compat (없으면 oauth) — 데이터 마이그레이션 불필요
- 롤백 시: 새로 만든 long-lived 계정 entry는 manual 삭제 또는 `/account:remove`
- shell function wrapper는 마커 기반이라 `account:release` 정리 가능

## 11. 미해결 사항

- POC 통과 여부 (8.2 절차로 실행 필요)
- `subscriptionType`/`rateLimitTier`를 사용자 입력 Plan에서 매핑하는 규칙 — 기존 `detect_plan_from_credential` 역방향 매핑 필요 (`account.py`에 추가)
- 일반 OAuth account의 `/account:export-token` 호출 시 토큰이 곧 만료된다는 점에 대한 UX (현재 access token은 8시간 후 만료. 별도 경고 메시지 필요)
