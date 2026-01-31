# Claude Code Multi-Account Manager

Claude Code 다중 계정 관리 플러그인입니다. 여러 계정을 로그아웃 없이 관리하고 전환할 수 있습니다.

## Quick Start

```bash
# 플러그인 설치
claude plugins install --local /path/to/multi-login-claude
# 또는 GitHub에서 직접 설치
claude plugins install ezhoon/multi-login-claude
```

설치 후 Claude Code에서 `/account` 명령어 사용 가능!

## 주요 기능

- **자동 계정 등록** - 세션 시작 시 현재 계정 자동 등록
- **계정 전환** - 로그아웃 없이 여러 계정 간 전환
- **사용량 모니터링** - 실시간 API 사용량 확인 (현재 세션 / 주간)
- **토큰 자동 갱신** - OAuth 토큰 만료 시 자동 갱신
- **Max5/Max20 플랜 지원** - 모든 Claude 플랜 구분

## 설치

### 방법 1: GitHub에서 설치 (권장)

```bash
claude plugins install ezhoon/multi-login-claude
```

### 방법 2: 로컬 설치

```bash
git clone https://github.com/ezhoon/multi-login-claude.git
claude plugins install --local ./multi-login-claude
```

### 방법 3: 수동 설치

1. 저장소 클론
```bash
git clone https://github.com/ezhoon/multi-login-claude.git ~/.claude/plugins/multi-login-claude
```

2. Claude Code 재시작

## 사용법

Claude Code 대화창에서 슬래시 명령어 사용:

| 명령어 | 설명 |
|--------|------|
| `/account` | 계정 목록 + 사용량 표시 |
| `/account-add [이름]` | 현재 계정 저장 |
| `/account-switch [id]` | 계정 전환 |
| `/account-check` | 토큰 상태 확인 |
| `/account-remove <id>` | 계정 삭제 |
| `/account-set-plan <id> <plan>` | Plan 설정 |

### 자동 계정 등록

플러그인 설치 후 Claude Code를 시작하면 **자동으로 현재 계정이 등록**됩니다:
- 이미 등록된 계정은 스킵
- Plan은 credential에서 자동 감지
- 이름은 displayName 또는 email에서 자동 생성

## 예시

### 계정 목록 확인

```
/account

  Claude 계정 목록
  ───────────────────────────────────────────────────────
  [1] ● work [Team] - 활성
      work@company.com
      현재 ██░░░░░░░░░░ 24% | ⏱ 4h 27m
      주간 ██████░░░░░░ 51% | ⏱ 87h 27m

  [2]   personal [Pro]
      me@gmail.com
      현재 ██░░░░░░░░░░ 17% | ⏱ 4h 4m
      주간 ██░░░░░░░░░░ 19% | ⏱ 110h 4m
  ───────────────────────────────────────────────────────
```

### 계정 전환

```
/account-switch

  계정 선택
  ───────────────────────────────────────────────────────
  [1] ● work [Team]
  [2]   personal [Pro]
  ───────────────────────────────────────────────────────
  번호를 입력하세요: 2

  계정 전환 완료
  personal (me@gmail.com)
  OAuth: 토큰 교체 완료

  Claude Code를 재시작해야 변경사항이 적용됩니다.
```

### 토큰 상태 확인

```
/account-check

  OAuth 토큰 상태 확인
  ──────────────────────────────────────────────────
  계정: work@company.com

  ✓ 토큰 상태: 유효

  현재 세션 사용량: 24%
  주간 사용량: 51%
```

토큰이 만료된 경우 자동으로 갱신:
```
  ✓ 토큰 상태: 자동 갱신됨
  → 토큰이 자동으로 갱신되었습니다.
```

## 플러그인 구조

```
multi-login-claude/
├── .claude-plugin/
│   └── plugin.json          # 플러그인 메타데이터
├── commands/
│   ├── account.md           # /account
│   ├── account-add.md       # /account-add
│   ├── account-switch.md    # /account-switch
│   ├── account-check.md     # /account-check
│   ├── account-remove.md    # /account-remove
│   └── account-set-plan.md  # /account-set-plan
├── hooks/
│   └── hooks.json           # SessionStart hook
├── hooks-handlers/
│   └── session-start.sh     # 자동 계정 등록 스크립트
└── account_manager.py       # 핵심 로직
```

## 데이터 저장 위치

| 항목 | 위치 |
|------|------|
| 계정 목록 | `~/.claude/accounts/index.json` |
| 프로필 | `~/.claude/accounts/profile_{id}.json` |
| Credential | `~/.claude/accounts/credential_{id}.json` |
| OAuth 토큰 | macOS Keychain |

## 제거

```bash
claude plugins uninstall account-manager
```

데이터 완전 삭제:
```bash
rm -rf ~/.claude/accounts
```

## 요구사항

- macOS (Keychain 사용)
- Python 3.8+
- Claude Code CLI

## 라이선스

MIT
