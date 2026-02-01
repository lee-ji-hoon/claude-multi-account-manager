# Release Skill

플러그인 새 버전을 배포합니다.

## 실행 단계

1. **버전 업데이트**
   - `.claude-plugin/plugin.json`의 version 필드를 증가
   - `.claude-plugin/marketplace.json`의 version 필드를 증가
   - Semantic Versioning 사용 (major.minor.patch)

2. **변경사항 커밋**
   ```bash
   git add .
   git commit -m "release: v{VERSION}

   {변경사항 요약}

   Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
   ```

3. **develop 브랜치 push**
   ```bash
   git push origin develop
   ```

4. **main 브랜치에 병합 및 push**
   ```bash
   git checkout main
   git merge develop --no-edit
   git push origin main
   git checkout develop
   ```

5. **배포 확인**
   - 마켓플레이스 업데이트: `claude plugin marketplace update lee-ji-hoon`
   - 플러그인 업데이트: `claude plugin update account@lee-ji-hoon`

## 버전 규칙

- **major** (x.0.0): 호환성 깨지는 변경
- **minor** (0.x.0): 새 기능 추가
- **patch** (0.0.x): 버그 수정

## 사용자 업데이트 방법

```bash
claude plugin marketplace update lee-ji-hoon
claude plugin update account@lee-ji-hoon
```
