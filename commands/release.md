---
description: 새 버전 릴리즈 (버전 업데이트 → 커밋 → 태그 → main 머지 → 푸시)
argument-hint: [버전] (예: 2.1.0)
allowed-tools: [Bash, Read, Edit, AskUserQuestion]
---

# Release

새 버전을 릴리즈합니다.

## Arguments

$ARGUMENTS

## Required Rules (필수)

1. **버전 형식**: semver 준수 (MAJOR.MINOR.PATCH)
2. **브랜치 전략**: develop → main 머지 후 태그
3. **마켓플레이스 캐시**: 반드시 업데이트 확인

## Instructions

### 1. 버전 결정

버전이 인자로 제공되지 않은 경우:
- 현재 버전 확인: `cat .claude-plugin/plugin.json | grep version`
- 캐시된 최신 버전 확인: `ls ~/.claude/plugins/cache/lee-ji-hoon/account/`
- AskUserQuestion으로 새 버전 입력받기

**중요**: 새 버전은 캐시된 모든 버전보다 높아야 함 (semver 비교)

### 2. plugin.json 버전 업데이트

```bash
# 현재 버전 확인
cat .claude-plugin/plugin.json
```

Edit 도구로 버전 수정:
```
"version": "이전버전" → "version": "새버전"
```

### 3. 커밋 및 태그 생성

```bash
# 스테이징
git add -A

# 커밋 (develop 브랜치)
git commit -m "release: v{버전}

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# 태그 생성
git tag -a v{버전} -m "v{버전}"

# develop 푸시
git push origin develop
```

### 4. main 브랜치 머지 (필수!)

```bash
# main으로 전환
git checkout main

# develop 머지
git merge develop

# main 푸시
git push origin main

# 태그 푸시
git push origin v{버전}

# develop으로 복귀
git checkout develop
```

### 5. 마켓플레이스 캐시 업데이트 확인

```bash
# 마켓플레이스 디렉토리 업데이트
cd ~/.claude/plugins/marketplaces/lee-ji-hoon && git pull origin main

# 버전 확인
cat .claude-plugin/plugin.json | grep version
```

### 6. 완료 안내

사용자에게 안내:
- Claude Code 재시작 필요
- `/plugin update account@lee-ji-hoon` 실행
- 또는 재시작 시 자동 업데이트

## Checklist

- [ ] plugin.json 버전 업데이트
- [ ] develop 브랜치에 커밋
- [ ] 태그 생성 (v{버전})
- [ ] **main 브랜치로 머지** (중요!)
- [ ] main 푸시
- [ ] 태그 푸시
- [ ] 마켓플레이스 캐시 업데이트 확인
