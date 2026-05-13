# multi-login-codex 설계 문서

**날짜:** 2026-05-05  
**상태:** 승인됨  
**참조:** multi-login-claude v2.3.8 (포팅 기준)

---

## 개요

Codex CLI용 다중 계정 관리 플러그인. 여러 OpenAI/ChatGPT 계정을 저장해두고 빠르게 전환할 수 있도록 한다. `multi-login-claude`의 아키텍처와 로직을 Codex 환경에 맞게 포팅한 독립 레포.

### 목표
- `codex login` 기반 OAuth 계정 여러 개를 저장/전환
- 세션 시작 시 만료 임박 토큰 자동 갱신
- oh-my-codex 스킬 시스템으로 `$account` 명령어 제공
- macOS Keychain 불필요 — 파일 기반(권한 600)으로 단순화

---

## 아키텍처

### 디렉토리 구조

```
multi-login-codex/
├── account_manager.py              # 진입점 (thin wrapper)
├── codex_account_manager/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py                   # 경로 상수, Plan 한도
│   ├── auth.py                     # auth.json 읽기/쓰기 (Keychain 없음)
│   ├── token.py                    # OAuth 토큰 갱신 (auth.openai.com)
│   ├── storage.py                  # index.json I/O
│   ├── api.py                      # OpenAI API (사용량 조회)
│   ├── logger.py                   # 로깅 유틸
│   ├── ui.py                       # 컬러/포맷 출력
│   ├── account.py                  # 계정 비즈니스 로직
│   └── commands/
│       ├── __init__.py
│       ├── list_cmd.py
│       ├── add_cmd.py
│       ├── switch_cmd.py
│       ├── remove_cmd.py
│       └── token_cmd.py            # check/refresh
├── hooks-handlers/
│   ├── session-start.sh            # auto-add + 만료 토큰 일괄 갱신
│   └── prompt-submit.sh            # 1시간 내 만료 토큰 갱신
├── skills/                         # oh-my-codex SKILL.md 형식
│   ├── list/SKILL.md
│   ├── add/SKILL.md
│   ├── switch/SKILL.md
│   ├── remove/SKILL.md
│   └── check/SKILL.md
├── install.sh                      # hooks.json 주입 + alias 설치
└── .codex-plugin/
    └── plugin.json
```

---

## 데이터 모델

### `~/.codex/auth.json` (Codex 원본 구조)

```json
{
  "auth_mode": "chatgpt",
  "OPENAI_API_KEY": null,
  "tokens": {
    "id_token": "...",
    "access_token": "eyJ...",
    "refresh_token": "rt_...",
    "account_id": "uuid"
  },
  "last_refresh": "2026-05-05T00:00:00Z"
}
```

### `~/.codex/accounts/index.json` (플러그인 계정 목록)

```json
{
  "accounts": [
    {
      "id": "abc12345",
      "name": "personal",
      "email": "user@gmail.com",
      "account_id": "e5cb942d-...",
      "plan": "Pro",
      "added_at": "2026-05-05T00:00:00Z",
      "last_used": "2026-05-05T00:00:00Z"
    }
  ]
}
```

### `~/.codex/accounts/auth_{id}.json` (저장된 계정 인증)

`~/.codex/auth.json`과 동일한 구조. 파일 권한 0o600.

---

## 핵심 모듈

### `auth.py` — 파일 기반 자격증명

```
read_auth()      → ~/.codex/auth.json 읽기
write_auth(data) → ~/.codex/auth.json 쓰기 (권한 600)
get_access_token()    → tokens.access_token
get_refresh_token()   → tokens.refresh_token
get_account_id()      → tokens.account_id
```

Claude의 `keychain.py` 역할. Keychain 없이 파일만 사용.

### `token.py` — OAuth 갱신

**갱신 엔드포인트:** `https://auth.openai.com/oauth/token`

```
POST https://auth.openai.com/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=rt_...
&client_id=<codex-client-id>
```

응답:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "rt_new...",
  "expires_in": 86400,
  "id_token": "eyJ..."
}
```

**주의:** refresh_token은 1회용. 갱신 즉시 새 토큰을 파일에 저장해야 한다.

**Race condition 방지:** `~/.codex/accounts/.refresh.lock` 파일 기반 락.

**에러 분류:**
- `permanent`: `invalid_grant`, HTTP 401 → 재로그인 필요
- `transient`: 5xx, 네트워크 오류 → exponential backoff 재시도 (최대 3회)

**soft-block:** 영구 실패 계정은 1시간 TTL로 재시도 억제.

### `storage.py` — 계정 인덱스

Claude의 `storage.py`와 동일한 패턴. `index.json` atomic write.

### `api.py` — 사용량 조회

OpenAI API로 사용량 조회. 엔드포인트는 구현 시 확인 필요.

---

## 계정 전환 흐름

```
account switch "work"
  1. index.json에서 "work" 계정 찾기
  2. ~/.codex/accounts/auth_{id}.json 읽기
  3. 토큰 만료 여부 확인 → 필요 시 갱신
  4. ~/.codex/auth.json 덮어쓰기 (원본 백업 후)
  5. last_used 업데이트
```

---

## 훅 연동

### `hooks.json` 주입 방식

`install.sh`가 `~/.codex/hooks.json`에 항목 추가:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [{ "type": "command", "command": "/path/to/session-start.sh" }]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [{ "type": "command", "command": "/path/to/prompt-submit.sh" }]
      }
    ]
  }
}
```

### session-start.sh

1. `account_manager.py auto-add` — 현재 Codex 계정 자동 등록
2. 모든 저장 계정 토큰 갱신 (만료 7시간 미만 시)

### prompt-submit.sh

현재 계정 토큰이 1시간 내 만료 시 갱신.

---

## 스킬 명령어

oh-my-codex 스킬 시스템(`$account` prefix):

| 명령어 | 동작 |
|--------|------|
| `$account list` | 계정 목록 + 사용량 표시 |
| `$account add [name]` | 현재 로그인 계정 저장 |
| `$account switch [id/name]` | 계정 전환 |
| `$account remove [id]` | 저장된 계정 삭제 |
| `$account check` | 현재 토큰 상태 확인 |

---

## 설치

```bash
git clone https://github.com/lee-ji-hoon/multi-login-codex
cd multi-login-codex
./install.sh
```

`install.sh` 동작:
1. `hooks.json`에 훅 주입 (기존 oh-my-codex 훅 보존)
2. 스킬 파일 `~/.codex/skills/account/`로 링크
3. shell alias `account` 설정 (`~/.zshrc`)

---

## Claude 플러그인과의 차이점 요약

| 항목 | multi-login-claude | multi-login-codex |
|------|-------------------|-------------------|
| 자격증명 저장소 | macOS Keychain | `~/.codex/auth.json` (파일) |
| 토큰 키 경로 | `claudeAiOauth.accessToken` | `tokens.access_token` |
| 갱신 엔드포인트 | `platform.claude.com/v1/oauth/token` | `auth.openai.com/oauth/token` |
| 계정 전환 대상 | `~/.claude.json` | `~/.codex/auth.json` |
| 저장 위치 | `~/.claude/accounts/` | `~/.codex/accounts/` |
| 훅 등록 | `settings.json` | `hooks.json` 주입 |
| Keychain 의존 | ✅ | ❌ |
| 플러그인 시스템 | Claude Code plugin | oh-my-codex skill |

---

## 미결 사항

- OpenAI OAuth client_id 확인 필요 (Codex CLI 소스코드에서 추출)
- 사용량 조회 API 엔드포인트 확인 필요
- oh-my-codex 플러그인 마켓플레이스 존재 여부 확인
