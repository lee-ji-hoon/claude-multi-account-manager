# Release Skill

플러그인 새 버전을 배포합니다. 변경사항을 분석하여 적절한 버전을 선택하고 릴리스 노트를 생성합니다.

## 실행 단계

### 1. 변경사항 분석

마지막 릴리스 이후 커밋들을 분석합니다:

```bash
git log $(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~10)..HEAD --oneline
```

### 2. 버전 선택 기준

| 버전 | 조건 | 예시 |
|------|------|------|
| **major** (x.0.0) | 호환성 깨지는 변경, API 변경 | 명령어 이름 변경, 데이터 구조 변경 |
| **minor** (0.x.0) | 새 기능 추가 | 새 명령어, 새 옵션 |
| **patch** (0.0.x) | 버그 수정, 문서 수정 | 오류 수정, README 업데이트 |

**커밋 메시지 키워드 분석:**
- `BREAKING`, `!:` → major
- `feat:`, `feature:` → minor
- `fix:`, `docs:`, `refactor:`, `chore:` → patch

### 3. 버전 업데이트

현재 버전을 읽고 새 버전으로 업데이트:

```bash
# 현재 버전 확인
cat .claude-plugin/plugin.json | grep version

# 파일 업데이트
# - .claude-plugin/plugin.json
# - .claude-plugin/marketplace.json
```

### 4. CHANGELOG.md 생성/업데이트

```markdown
## [x.x.x] - YYYY-MM-DD

### Added (minor)
- 새로운 기능

### Changed (minor/major)
- 변경된 기능

### Fixed (patch)
- 버그 수정

### Breaking Changes (major)
- 호환성 깨지는 변경
```

### 5. 커밋 및 배포

```bash
# 커밋
git add .
git commit -m "release: v{VERSION}

{CHANGELOG 내용}

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Push
git push origin develop
git checkout main && git merge develop --no-edit && git push origin main
git checkout develop

# 태그 생성
git tag v{VERSION}
git push origin v{VERSION}
```

### 6. 배포 확인

```bash
claude plugin marketplace update lee-ji-hoon
claude plugin update account@lee-ji-hoon
```

## 사용 예시

사용자: "배포해줘" 또는 "/release"

1. 변경사항 분석:
   ```
   최근 커밋:
   - fix: OAuth endpoint 수정
   - docs: README 간소화
   ```

2. 버전 추천:
   ```
   현재 버전: 1.2.0
   변경 유형: patch (버그 수정, 문서)
   추천 버전: 1.2.1
   ```

3. 사용자에게 확인:
   - patch (1.2.1) - 권장
   - minor (1.3.0)
   - major (2.0.0)

4. CHANGELOG 생성 및 배포

## Release Note 템플릿

```markdown
# v{VERSION} Release Notes

## What's Changed

### 🐛 Bug Fixes
- OAuth 토큰 갱신 엔드포인트 수정

### 📝 Documentation
- README 간소화 및 Mermaid 다이어그램 추가

## Full Changelog
https://github.com/lee-ji-hoon/claude-multi-account-manager/compare/v{PREV}...v{VERSION}
```
