# multi-login-claude 프로젝트

## 프로젝트 개요
Claude Code 다중 계정 관리 플러그인. Python으로 작성되었으며 macOS Keychain을 사용합니다.

## 주요 파일
- `account_manager.py`: Entry point (얇은 래퍼)
- `claude_account_manager/`: 핵심 패키지
  - `config.py`: 상수, 경로, Plan 제한
  - `ui.py`: 색상, 포맷팅 유틸리티
  - `keychain.py`: macOS Keychain 연동
  - `storage.py`: 파일 I/O (index.json, claude.json, atomic write)
  - `token.py`: OAuth 토큰 관리
  - `api.py`: Anthropic API 호출
  - `account.py`: 계정 비즈니스 로직
  - `logger.py`: 로깅 (파일 회전, 보안)
  - `commands/`: CLI 명령어 핸들러
- `hooks-handlers/`: Hook 스크립트 (session-start, prompt-submit)
- `.claude-plugin/plugin.json`: 플러그인 메타데이터 (v2.1.4)

## 릴리즈 규칙 (필수)
**릴리즈 시 반드시 `/account:release` 스킬을 사용할 것!**

## 주요 명령어
- `/account:list`: 계정 목록 + 사용량
- `/account:add [이름]`: 현재 계정 저장
- `/account:switch [id]`: 계정 전환
- `/account:remove [id]`: 계정 삭제
- `/account:set-plan [id] [plan]`: Plan 설정
- `/account:check`: 토큰 상태 확인

## 데이터 위치
- 계정 정보: `~/.claude/accounts/index.json`
- OAuth 토큰: macOS Keychain
- 프로필: `~/.claude/accounts/profile_{id}.json`
- 자격증명: `~/.claude/accounts/credential_{id}.json`

## 기술 스택
- Python 3 (표준 라이브러리만 사용)
- macOS Keychain (`security` CLI)
- Claude Code Plugin System

## 코드 품질 평가

### 보안 ✓
- Atomic write (임시 파일 → rename)
- 파일 권한: 0o600 (600)
- Keychain으로 토큰 안전 저장
- OAuth 토큰 회전 (refresh token은 일회성)

### 안정성 ✓
- 로그 파일 회전 (512KB 초과 시)
- 예외 처리 포괄적
- 타임아웃 설정 (10초)

### 구조 ✓
- 모듈화: 7개 핵심 모듈
- Commands: 13개 명령어
- Hooks: 2개
- Skills: release.md

## 발견된 문제

### 1. pyproject.toml 버전 불일치 ✓ (수정 완료)
- 수정 전: 1.0.0
- 수정 후: 2.1.4

### 2. CHANGELOG 미갱신 (보고 완료)
- v0.1.0까지만 기록
- v2.0.0~v2.1.4 내용 누락
- 8개 릴리즈 태그: v0.0.1, v0.1.0, v2.0.0, v2.1.0~v2.1.4

## Git 상태
- 현재 브랜치: develop
- 변경 파일: 5개 (pyproject.toml, install.sh, marketplace.json, token.py, api.py)
- 최신 태그: v2.1.4

## 최종 검사 결과 (2026-03-01)

### 수정 완료
1. ✓ pyproject.toml: 1.0.0 → 2.1.4
2. ✓ install.sh: 1.0.0 → 2.1.4
3. ✓ marketplace.json: 0.1.0 → 2.1.4
4. ✓ token.py: User-Agent 1.0 → 2.1.4 (2개 위치)
5. ✓ api.py: User-Agent 1.0 → 2.1.4

### 미해결 문제
- CHANGELOG.md: v0.1.0 이후 버전 미기록

### 코드 품질 평가
- 보안: 우수 (Atomic write, Keychain, 파일 권한 0o600)
- 안정성: 우수 (로그 회전, 예외 처리, 타임아웃)
- 구조: 우수 (모듈화, 13개 명령어, 2개 Hook)
