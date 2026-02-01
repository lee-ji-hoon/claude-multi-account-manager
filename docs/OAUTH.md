# OAuth Token Refresh

Claude Code의 OAuth 토큰 갱신 메커니즘을 설명합니다.

## 참고한 소스 코드

| 파일 | 역할 |
|------|------|
| `claude_account_manager/token.py` | 토큰 갱신 핵심 로직 (`refresh_access_token`) |
| `claude_account_manager/api.py` | API 호출 시 자동 갱신 (`_fetch_usage_from_api`) |
| `hooks-handlers/session-start.sh` | 세션 시작 시 갱신 트리거 |

## API 명세

### 엔드포인트

```
POST https://platform.claude.com/v1/oauth/token
```

### 요청

**Headers:**
```
Content-Type: application/x-www-form-urlencoded
User-Agent: claude-account-manager/1.0
```

**Body (form-urlencoded):**
| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `grant_type` | `refresh_token` | 고정값 |
| `refresh_token` | `sk-ant-ort01-...` | 저장된 리프레시 토큰 |
| `client_id` | `9d1c250a-e61b-44d9-88ed-5944d1962f5e` | Claude Code 공식 OAuth Client ID |

### 응답

**성공 (200 OK):**
```json
{
  "token_type": "Bearer",
  "access_token": "sk-ant-oat01-...",
  "refresh_token": "sk-ant-ort01-...",
  "expires_in": 28800,
  "scope": "user:inference user:mcp_servers user:profile user:sessions:claude_code"
}
```

| 필드 | 설명 |
|------|------|
| `access_token` | 새로운 액세스 토큰 (API 인증용) |
| `refresh_token` | 새로운 리프레시 토큰 (다음 갱신용) |
| `expires_in` | 만료 시간 (초), 기본 28800초 = 8시간 |
| `scope` | 토큰 권한 범위 |

## 토큰 특성

- **액세스 토큰 유효기간**: 8시간 (28800초)
- **리프레시 토큰**: 일회성 (갱신 시 새 토큰 발급, 기존 토큰 무효화)
- **토큰 형식**: `sk-ant-oat01-...` (access), `sk-ant-ort01-...` (refresh)

## 갱신 시점

### 1. 세션 시작 (SessionStart Hook)

모든 저장된 계정의 토큰을 무조건 갱신합니다.

```
세션 시작 → session-start.sh → account_manager.py refresh-all
```

### 2. 메시지 입력 (UserPromptSubmit Hook)

만료 1시간 이내인 토큰만 선택적으로 갱신합니다.

```
메시지 입력 → prompt-submit.sh → account_manager.py refresh-expiring
```

### 3. API 호출 실패 시 (자동 갱신)

401 응답 시 자동으로 토큰을 갱신하고 재시도합니다.

```python
# api.py:231-240
except urllib.error.HTTPError as e:
    if e.code == 401:
        new_credential, refresh_error = refresh_access_token(credential, credential_file=credential_file)
        if new_credential:
            return _fetch_usage_from_api(new_credential, include_token_status, credential_file=None)
```

## curl 예시

```bash
curl -X POST https://platform.claude.com/v1/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=YOUR_REFRESH_TOKEN" \
  -d "client_id=9d1c250a-e61b-44d9-88ed-5944d1962f5e"
```

## 토큰 저장 위치

| 계정 유형 | 저장 위치 |
|----------|----------|
| 현재 로그인 계정 | macOS Keychain (`claude.ai`) |
| 저장된 계정 | `~/.claude/accounts/credential_{id}.json` |

## 에러 처리

| HTTP 코드 | 의미 | 처리 |
|----------|------|------|
| 200 | 성공 | 새 토큰 저장 |
| 401 | 토큰 만료/무효 | 재로그인 필요 |
| 403 | 권한 없음 | 재로그인 필요 |
| 5xx | 서버 오류 | 재시도 |

## 관련 문서

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 전체 아키텍처 및 동작 원리
