# /account:export - 계정 정보 추출하기

현재 로그인된 계정 정보를 JSON 형식으로 추출합니다.
다른 컴퓨터에서 `/account:import`로 가져올 수 있습니다.

## 사용법

```bash
/account:export
```

## 동작 방식

1. 현재 로그인된 계정의 프로필 정보 추출
2. macOS Keychain에서 OAuth 토큰 추출
3. 통합 JSON 형식으로 생성
4. 자동으로 클립보드에 복사 (macOS)

## 출력 예시

```json
{
  "profile": {
    "accountUuid": "9500114a-fb87-4f64-9920-0fefe644f35c",
    "emailAddress": "user@example.com",
    "organizationUuid": "12962499-59a4-40ac-baf0-30a6b3bcc340",
    "displayName": "사용자명",
    "organizationRole": "admin"
  },
  "credential": {
    "access_token": "sk-...",
    "refresh_token": "...",
    "expires_at": "2026-02-02T08:00:00Z"
  }
}
```

## 다음 단계

추출한 JSON을 다른 컴에서 사용하기:
```bash
# 다른 컴에서
/account:import
# 클립보드(Cmd+V)에서 JSON 붙여넣기
```

또는 직접 파일로 저장:
```bash
/account:export > ~/Desktop/account-export.json
# 다른 컴에서
/account:import ~/Desktop/account-export.json
```

## 보안 주의

- 추출된 JSON에는 유효한 OAuth 토큰이 포함됩니다
- 안전한 방식으로 다른 컴에 전달하세요
- 신뢰할 수 있는 네트워크 경로를 사용하세요

## 관련 명령어

- `/account:import` - 계정 정보 가져오기
- `/account:list` - 가져온 계정 목록 보기
- `/account:switch` - 계정 전환하기
