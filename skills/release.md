# Release Skill

플러그인 새 버전을 배포합니다.

## 실행 흐름

### 1. 변경사항 분석

```bash
# 마지막 태그 이후 커밋 확인
git log $(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~20)..HEAD --oneline
```

### 2. 버전 결정

| 타입 | 버전 | 커밋 키워드 |
|------|------|-------------|
| Breaking Change | major (x.0.0) | `BREAKING`, `!:` |
| New Feature | minor (0.x.0) | `feat:` |
| Bug Fix / Docs | patch (0.0.x) | `fix:`, `docs:`, `refactor:` |

### 3. CHANGELOG 작성 (Claude Code 스타일)

```markdown
## [x.x.x] - YYYY-MM-DD

### What's changed

**Added**
- 새 기능 설명

**Fixed**
- 버그 수정 설명

**Changed**
- 변경사항 설명

**Improved**
- 개선사항 설명

### Commits

```
{hash} {message}
{hash} {message}
```

### Full Changelog

https://github.com/lee-ji-hoon/claude-multi-account-manager/compare/v{prev}...v{new}
```

### 4. 버전 업데이트

```bash
# 파일 수정
# - .claude-plugin/plugin.json
# - .claude-plugin/marketplace.json
```

### 5. 배포

```bash
git add .
git commit -m "release: v{VERSION}

{What's changed 요약}

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git push origin develop
git checkout main && git merge develop --no-edit && git push origin main
git tag v{VERSION} && git push origin v{VERSION}
git checkout develop
```

### 6. 확인

```bash
claude plugin marketplace update lee-ji-hoon
claude plugin update account@lee-ji-hoon
```

## 릴리스 노트 작성 규칙

1. **간결하게**: 각 항목 50자 이내
2. **사용자 관점**: 기술 용어보다 기능 설명
3. **커밋 나열**: 해시와 메시지 포함
4. **비교 링크**: 이전 버전과 비교 URL 제공
