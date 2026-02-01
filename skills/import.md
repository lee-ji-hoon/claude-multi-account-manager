# /account:import - 계정 가져오기

다른 컴퓨터의 계정 정보를 현재 Claude Code에 가져옵니다.

## 사용법

### 1. 표준 export 형식 가져오기 (권장)
```bash
# 클립보드에서 붙여넣기
/account:import

# 또는 JSON 문자열로 직접 가져오기
/account:import '{"profile": {...}, "credential": {...}}'

# 또는 파일에서 가져오기
/account:import /path/to/export.json
```

### 2. claude_auth.json 형식 가져오기
`~/.claude/CLAUDE.md`의 `claude_auth.json` 파일을 사용할 수 있습니다.
```bash
/account:import ~/Downloads/claude_auth.json

# 파일 경로 대신 JSON 직접 입력도 가능:
/account:import '{"oauthAccount": {...}, ...}'
```

## 지원되는 형식

### 표준 형식 (권장)
```json
{
  "profile": {
    "accountUuid": "...",
    "emailAddress": "user@example.com",
    "displayName": "사용자명",
    ...
  },
  "credential": {
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": "..."
  }
}
```

### claude_auth.json 형식
```json
{
  "oauthAccount": {
    "accountUuid": "...",
    "emailAddress": "user@example.com",
    "displayName": "사용자명",
    ...
  },
  ...
}
```
*(credential은 별도로 입력해야 함)*

## 순서

1. **표준 형식** 사용: `/account export`로 다른 컴에서 추출한 JSON 사용
2. **단계별 입력**: 프로필과 credential을 각각 입력
3. **파일 경로**: JSON 파일 경로 직접 지정

## 관련 명령어

- `/account:list` - 가져온 계정 목록 보기
- `/account:export` - 현재 계정 정보 추출하기
- `/account:switch` - 계정 전환하기
