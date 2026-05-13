# Long-lived OAuth Token 지원 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `claude setup-token`이 발급하는 1년 유효 OAuth 토큰(long-lived)을 multi-account-manager에 일반 OAuth 계정과 동등하게 등록·전환·관리할 수 있도록 한다.

**Architecture:** 기존 `claudeAiOauth` schema를 재사용한 wrap 방식 (refreshToken="" + expiresAt=발급+365일) + `index.json`에 `tokenType` 필드 신설. switch 시 keychain 덮어쓰기 + `--shell-export` 플래그로 `CLAUDE_CODE_OAUTH_TOKEN` env 라인을 stdout 출력 → `.zshrc` function wrapper가 eval. SessionStart hook과 `check_token_status`는 `tokenType == "long-lived"`이면 refresh/usage API 호출 skip.

**Tech Stack:** Python 3 표준 라이브러리만 사용 (`urllib`, `json`, `getpass`, `unittest`), macOS Keychain `security` CLI, zsh function

**Spec 참조:** `docs/superpowers/specs/2026-05-13-long-lived-token-design.md`

---

## 파일 구조

### 신규
- `claude_account_manager/long_lived.py` — long-lived 토큰 유틸 (wrap, validate, dday, plan mapping, is_long_lived)
- `claude_account_manager/commands/export_token_cmd.py` — `export-token` 명령 핸들러
- `tests/__init__.py` — 빈 파일
- `tests/test_long_lived.py` — long-lived 유닛 테스트
- `tests/test_switch_long_lived.py` — switch 분기 유닛 테스트
- `scripts/poc_long_lived.sh` — POC 검증 스크립트 (수동 실행)

### 수정
- `claude_account_manager/commands/add_cmd.py` — 유형 선택 + `cmd_add_long_lived`
- `claude_account_manager/commands/switch_cmd.py` — `shell_export` 인자 + tokenType 분기
- `claude_account_manager/commands/list_cmd.py` — Type 컬럼 + D-day + usage skip
- `claude_account_manager/commands/token_cmd.py` — `cmd_check` + `cmd_refresh_all` long-lived skip
- `claude_account_manager/commands/__init__.py` — `export-token` 서브커맨드, `--shell-export` 옵션
- `claude_account_manager/account.py` — `generate_long_lived_account_id` 헬퍼
- `hooks-handlers/session-start.sh` — function wrapper(`account:switch`, `account:export-token`) + 만료 경고 호출
- `skills/account-add/SKILL.md`, `skills/account-switch/SKILL.md`, `skills/account-list/SKILL.md` — 본문 업데이트
- `skills/account-export-token/SKILL.md` — 신규
- `README.md`, `README.ko.md` — long-lived 섹션 추가

---

## Task 0: POC 검증 (구현 전 필수)

**Spec 8.2 참조.** 구현 전에 `claude setup-token` 토큰이 keychain wrap 방식으로 동작하는지 5분 안에 검증.

**Files:**
- Create: `scripts/poc_long_lived.sh`

- [ ] **Step 1: POC 스크립트 작성**

`scripts/poc_long_lived.sh`:

```bash
#!/usr/bin/env bash
# Long-lived token keychain wrap POC
# Usage: bash scripts/poc_long_lived.sh
set -e

echo "1. claude setup-token 으로 토큰을 발급하고 prompt에 paste하세요."
echo "   터미널 다른 창에서: claude setup-token"
read -rsp "토큰: " TOKEN
echo

if [[ "$TOKEN" != sk-ant-* ]]; then
  echo "[FAIL] 토큰 포맷이 예상과 다릅니다 (sk-ant- prefix 아님)"
  exit 1
fi

echo "[A3] 토큰 포맷 OK"

echo "[A2] /api/oauth/usage 호출"
HTTP_CODE=$(curl -s -o /tmp/poc_usage.json -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "anthropic-beta: oauth-2025-04-20" \
  https://api.anthropic.com/api/oauth/usage)
echo "    HTTP $HTTP_CODE"
cat /tmp/poc_usage.json
echo

EXPIRES_MS=$(python3 -c "from datetime import datetime, timedelta; print(int((datetime.now()+timedelta(days=365)).timestamp()*1000))")
WRAPPED=$(python3 -c "
import json, sys
print(json.dumps({'claudeAiOauth': {
    'accessToken': sys.argv[1],
    'refreshToken': '',
    'expiresAt': int(sys.argv[2]),
    'subscriptionType': 'max',
    'rateLimitTier': 'default_claude_max_20x',
}}, ensure_ascii=False))
" "$TOKEN" "$EXPIRES_MS")

echo "[A1/A4] keychain wrap → claude 기동 테스트"
echo "    아래 명령을 별도 터미널에서 직접 실행하여 검증:"
echo "    security delete-generic-password -s 'Claude Code-credentials' -a \$USER 2>/dev/null"
echo "    security add-generic-password -s 'Claude Code-credentials' -a \$USER -w '<WRAPPED_JSON>'"
echo "    claude --print 'hello'"
echo
echo "WRAPPED_JSON:"
echo "$WRAPPED"
```

- [ ] **Step 2: POC 실행 안내 + 결과 기록**

```bash
chmod +x scripts/poc_long_lived.sh
bash scripts/poc_long_lived.sh
```

POC 결과를 `docs/superpowers/specs/2026-05-13-long-lived-token-design.md` Section 11에 추가:

```markdown
## POC 결과 (YYYY-MM-DD)
- A1 (keychain wrap 동작): PASS/FAIL
- A2 (usage API 응답): HTTP <code>
- A3 (토큰 prefix): <실제 prefix>
- A4 (refresh 미시도): PASS/FAIL
```

- [ ] **Step 3: 결과에 따른 분기**

- A1 PASS + A4 PASS → 본 plan 그대로 진행
- A1 FAIL → switch task에서 keychain wrap 코드 제거, export 안내만 유지 (Task 8에 표시)
- A2 HTTP 200 → list task의 usage skip 분기 제거 (Task 7에 표시)

- [ ] **Step 4: Commit**

```bash
git add scripts/poc_long_lived.sh docs/superpowers/specs/2026-05-13-long-lived-token-design.md
git commit -m "chore: long-lived token POC 스크립트 추가 + 결과 기록"
```

---

## Task 1: `long_lived.py` 토큰 포맷 검증

**Files:**
- Create: `claude_account_manager/long_lived.py`
- Create: `tests/__init__.py` (빈 파일)
- Create: `tests/test_long_lived.py`

- [ ] **Step 1: 테스트 작성**

`tests/__init__.py`: 빈 파일

`tests/test_long_lived.py`:

```python
import unittest
from claude_account_manager.long_lived import validate_token_format


class TestValidateTokenFormat(unittest.TestCase):
    def test_accepts_sk_ant_oat_prefix(self):
        self.assertTrue(validate_token_format("sk-ant-oat01-abc123"))

    def test_accepts_sk_ant_prefix_general(self):
        # POC에서 다른 sk-ant- prefix가 나올 수 있음
        self.assertTrue(validate_token_format("sk-ant-anything-xyz"))

    def test_rejects_empty(self):
        self.assertFalse(validate_token_format(""))

    def test_rejects_whitespace_only(self):
        self.assertFalse(validate_token_format("   "))

    def test_rejects_wrong_prefix(self):
        self.assertFalse(validate_token_format("bearer-token-foo"))

    def test_rejects_none(self):
        self.assertFalse(validate_token_format(None))

    def test_strips_whitespace(self):
        self.assertTrue(validate_token_format("  sk-ant-oat01-x  "))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/koni/Desktop/ai-work/claude-multi-account-manager
python3 -m unittest tests.test_long_lived -v
```

Expected: `ImportError: cannot import name 'validate_token_format'`

- [ ] **Step 3: 구현**

`claude_account_manager/long_lived.py`:

```python
"""
Long-lived OAuth token (claude setup-token) 전용 유틸
"""


def validate_token_format(token):
    """long-lived 토큰 포맷 검증

    `claude setup-token`이 발급하는 토큰은 sk-ant- prefix를 가진다.
    구체적 sub-prefix(oat01 등)는 시간이 지나며 바뀔 수 있으므로 sk-ant- 만 검증.
    """
    if not token:
        return False
    if not isinstance(token, str):
        return False
    stripped = token.strip()
    if not stripped:
        return False
    return stripped.startswith("sk-ant-")
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m unittest tests.test_long_lived -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add claude_account_manager/long_lived.py tests/__init__.py tests/test_long_lived.py
git commit -m "feat: long-lived 토큰 포맷 검증 유틸 추가"
```

---

## Task 2: `long_lived.py` 토큰 wrap

`claude setup-token` 토큰을 기존 `claudeAiOauth` schema로 wrap.

**Files:**
- Modify: `claude_account_manager/long_lived.py`
- Modify: `tests/test_long_lived.py`

- [ ] **Step 1: 테스트 추가**

`tests/test_long_lived.py` 끝에 추가:

```python
from claude_account_manager.long_lived import wrap_long_lived_token, plan_to_subscription_type


class TestPlanToSubscriptionType(unittest.TestCase):
    def test_max20(self):
        self.assertEqual(plan_to_subscription_type("Max20"),
                         ("max", "default_claude_max_20x"))

    def test_max5(self):
        self.assertEqual(plan_to_subscription_type("Max5"),
                         ("max", "default_claude_max_5x"))

    def test_pro(self):
        self.assertEqual(plan_to_subscription_type("Pro"),
                         ("pro", ""))

    def test_team(self):
        self.assertEqual(plan_to_subscription_type("Team"),
                         ("team", ""))

    def test_free(self):
        self.assertEqual(plan_to_subscription_type("Free"),
                         ("free", ""))

    def test_unknown_defaults_to_free(self):
        self.assertEqual(plan_to_subscription_type("Foo"),
                         ("free", ""))


class TestWrapLongLivedToken(unittest.TestCase):
    def test_schema_shape(self):
        wrapped = wrap_long_lived_token("sk-ant-oat01-abc", "Max20")
        self.assertIn("claudeAiOauth", wrapped)
        oauth = wrapped["claudeAiOauth"]
        self.assertEqual(oauth["accessToken"], "sk-ant-oat01-abc")
        self.assertEqual(oauth["refreshToken"], "")
        self.assertEqual(oauth["subscriptionType"], "max")
        self.assertEqual(oauth["rateLimitTier"], "default_claude_max_20x")
        self.assertIsInstance(oauth["expiresAt"], int)

    def test_expires_at_is_about_one_year_future(self):
        import time
        before_ms = int(time.time() * 1000)
        wrapped = wrap_long_lived_token("sk-ant-oat01-abc", "Pro")
        after_ms = int(time.time() * 1000)
        expires = wrapped["claudeAiOauth"]["expiresAt"]
        one_year_ms = 365 * 24 * 60 * 60 * 1000
        self.assertGreaterEqual(expires, before_ms + one_year_ms - 5000)
        self.assertLessEqual(expires, after_ms + one_year_ms + 5000)

    def test_pro_plan_subscription_type(self):
        wrapped = wrap_long_lived_token("sk-ant-oat01-x", "Pro")
        self.assertEqual(wrapped["claudeAiOauth"]["subscriptionType"], "pro")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m unittest tests.test_long_lived -v
```

Expected: `ImportError` for `wrap_long_lived_token`

- [ ] **Step 3: 구현**

`claude_account_manager/long_lived.py` 끝에 추가:

```python
from datetime import datetime, timedelta


LONG_LIVED_VALIDITY_DAYS = 365


def plan_to_subscription_type(plan):
    """Plan name → (subscriptionType, rateLimitTier) 매핑

    detect_plan_from_credential의 역방향. 사용자 입력 Plan으로부터
    credential의 subscriptionType과 rateLimitTier를 생성한다.
    """
    plan_map = {
        "Max20": ("max", "default_claude_max_20x"),
        "Max5": ("max", "default_claude_max_5x"),
        "Pro": ("pro", ""),
        "Team": ("team", ""),
        "Free": ("free", ""),
    }
    return plan_map.get(plan, ("free", ""))


def wrap_long_lived_token(token, plan, validity_days=LONG_LIVED_VALIDITY_DAYS):
    """long-lived 토큰을 claudeAiOauth schema로 wrap

    refreshToken은 빈 문자열(없음 의미). expiresAt은 발급 시점 + validity_days.
    Plan에 따라 subscriptionType/rateLimitTier를 채운다.
    """
    sub_type, rate_tier = plan_to_subscription_type(plan)
    expires_at_ms = int((datetime.now() + timedelta(days=validity_days)).timestamp() * 1000)
    return {
        "claudeAiOauth": {
            "accessToken": token.strip(),
            "refreshToken": "",
            "expiresAt": expires_at_ms,
            "subscriptionType": sub_type,
            "rateLimitTier": rate_tier,
        }
    }
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m unittest tests.test_long_lived -v
```

Expected: all passed (10+ tests)

- [ ] **Step 5: Commit**

```bash
git add claude_account_manager/long_lived.py tests/test_long_lived.py
git commit -m "feat: long-lived 토큰 wrap + plan 매핑 함수 추가"
```

---

## Task 3: `long_lived.py` 만료 D-day 계산 + `is_long_lived_account`

**Files:**
- Modify: `claude_account_manager/long_lived.py`
- Modify: `tests/test_long_lived.py`

- [ ] **Step 1: 테스트 추가**

`tests/test_long_lived.py` 끝에 추가:

```python
from claude_account_manager.long_lived import (
    format_expiry_dday,
    is_long_lived_account,
    EXPIRY_WARN_DAYS,
    EXPIRY_DANGER_DAYS,
)


class TestIsLongLivedAccount(unittest.TestCase):
    def test_oauth_default_when_missing(self):
        self.assertFalse(is_long_lived_account({"id": "x"}))

    def test_explicit_oauth(self):
        self.assertFalse(is_long_lived_account({"tokenType": "oauth"}))

    def test_long_lived(self):
        self.assertTrue(is_long_lived_account({"tokenType": "long-lived"}))


class TestFormatExpiryDday(unittest.TestCase):
    def _expires_in(self, days):
        from datetime import datetime, timedelta
        return int((datetime.now() + timedelta(days=days)).timestamp() * 1000)

    def test_normal(self):
        label, severity = format_expiry_dday(self._expires_in(200))
        self.assertEqual(label, "D-200")
        self.assertEqual(severity, "normal")

    def test_warn_at_30(self):
        label, severity = format_expiry_dday(self._expires_in(25))
        self.assertEqual(severity, "warn")

    def test_danger_at_7(self):
        label, severity = format_expiry_dday(self._expires_in(3))
        self.assertEqual(severity, "danger")

    def test_expired(self):
        label, severity = format_expiry_dday(self._expires_in(-1))
        self.assertEqual(label, "만료됨")
        self.assertEqual(severity, "expired")

    def test_today_is_d0_danger(self):
        label, severity = format_expiry_dday(self._expires_in(0))
        self.assertEqual(label, "D-0")
        self.assertEqual(severity, "danger")

    def test_severity_thresholds_constants(self):
        self.assertEqual(EXPIRY_WARN_DAYS, 30)
        self.assertEqual(EXPIRY_DANGER_DAYS, 7)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m unittest tests.test_long_lived -v
```

Expected: `ImportError`

- [ ] **Step 3: 구현**

`claude_account_manager/long_lived.py` 끝에 추가:

```python
EXPIRY_WARN_DAYS = 30
EXPIRY_DANGER_DAYS = 7


def is_long_lived_account(account_entry):
    """account index entry가 long-lived 계정인지 판정

    tokenType 필드가 없으면 oauth (backward compat).
    """
    if not account_entry:
        return False
    return account_entry.get("tokenType", "oauth") == "long-lived"


def format_expiry_dday(expires_at_ms):
    """만료까지 D-day와 severity 레벨 반환

    Returns:
        tuple[str, str]: (라벨, severity)
        severity: "normal" | "warn" | "danger" | "expired"
    """
    if not expires_at_ms:
        return ("?", "normal")
    expires = datetime.fromtimestamp(expires_at_ms / 1000)
    delta = expires - datetime.now()
    days = delta.days  # 음수 가능
    # 0~24시간 남은 케이스는 days==0
    if delta.total_seconds() < 0 and days < 0:
        return ("만료됨", "expired")
    label = f"D-{days}"
    if days <= EXPIRY_DANGER_DAYS:
        severity = "danger"
    elif days <= EXPIRY_WARN_DAYS:
        severity = "warn"
    else:
        severity = "normal"
    return (label, severity)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m unittest tests.test_long_lived -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add claude_account_manager/long_lived.py tests/test_long_lived.py
git commit -m "feat: long-lived 만료 D-day 계산 + is_long_lived_account 헬퍼"
```

---

## Task 4: `account.py` long-lived ID 충돌 회피 헬퍼

기존 `generate_account_id`는 일반 OAuth용. long-lived는 동일 email로 일반 계정이 있을 수 있으므로 `_token` suffix.

**Files:**
- Modify: `claude_account_manager/account.py`
- Create: `tests/test_account_ids.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_account_ids.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestGenerateLongLivedAccountId(unittest.TestCase):
    def _mock_index(self, accounts):
        return {"accounts": accounts, "activeAccountId": None}

    def test_no_conflict_appends_token_suffix(self):
        from claude_account_manager import account as account_mod
        with patch.object(account_mod, "load_index",
                          return_value=self._mock_index([])):
            self.assertEqual(
                account_mod.generate_long_lived_account_id("joel@x.com"),
                "joel_token")

    def test_conflict_with_existing_oauth_account(self):
        from claude_account_manager import account as account_mod
        with patch.object(account_mod, "load_index",
                          return_value=self._mock_index([
                              {"id": "joel", "tokenType": "oauth"}
                          ])):
            self.assertEqual(
                account_mod.generate_long_lived_account_id("joel@x.com"),
                "joel_token")

    def test_conflict_with_existing_long_lived(self):
        from claude_account_manager import account as account_mod
        with patch.object(account_mod, "load_index",
                          return_value=self._mock_index([
                              {"id": "joel_token", "tokenType": "long-lived"}
                          ])):
            self.assertEqual(
                account_mod.generate_long_lived_account_id("joel@x.com"),
                "joel_token_2")

    def test_multiple_collisions(self):
        from claude_account_manager import account as account_mod
        with patch.object(account_mod, "load_index",
                          return_value=self._mock_index([
                              {"id": "joel_token"},
                              {"id": "joel_token_2"},
                              {"id": "joel_token_3"},
                          ])):
            self.assertEqual(
                account_mod.generate_long_lived_account_id("joel@x.com"),
                "joel_token_4")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m unittest tests.test_account_ids -v
```

Expected: `AttributeError: module ... has no attribute 'generate_long_lived_account_id'`

- [ ] **Step 3: 구현**

`claude_account_manager/account.py` 끝에 추가:

```python
def generate_long_lived_account_id(email):
    """long-lived 토큰 계정용 id 생성

    기본: {email_base}_token
    동일 id가 이미 있으면 _token_2, _token_3 ...
    """
    base = email.split("@")[0].replace(".", "_").replace("+", "_").lower()
    existing_ids = {acc.get("id") for acc in load_index().get("accounts", [])}

    candidate = f"{base}_token"
    if candidate not in existing_ids:
        return candidate

    n = 2
    while True:
        candidate = f"{base}_token_{n}"
        if candidate not in existing_ids:
            return candidate
        n += 1
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m unittest tests.test_account_ids -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add claude_account_manager/account.py tests/test_account_ids.py
git commit -m "feat: long-lived 토큰 계정용 ID 생성 헬퍼 추가"
```

---

## Task 5: `/account:add` 유형 선택 분기

기존 `cmd_add`에 진입 prompt 추가. `cmd_add_long_lived`를 신설.

**Files:**
- Modify: `claude_account_manager/commands/add_cmd.py`

- [ ] **Step 1: `cmd_add_long_lived` 함수 추가**

`claude_account_manager/commands/add_cmd.py` 상단 import 추가:

```python
import getpass
from ..long_lived import (
    validate_token_format,
    wrap_long_lived_token,
)
from ..account import generate_long_lived_account_id
```

파일 끝에 새 함수 추가:

```python
def cmd_add_long_lived():
    """Long-lived 토큰(claude setup-token 발급) 등록

    토큰을 paste 입력받고, email/name/plan은 수동 입력.
    """
    print()
    print(c(Colors.BOLD, "  Long-lived 토큰 등록"))
    print(c(Colors.DIM, "  " + "─" * 40))
    print(c(Colors.DIM, "  발급 방법:"))
    print(c(Colors.DIM, "    터미널에서 `claude setup-token` 실행"))
    print(c(Colors.DIM, "    OAuth 후 출력되는 토큰을 복사하여 아래에 paste"))
    print()

    try:
        token = getpass.getpass("  토큰 paste (입력 숨김): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    if not validate_token_format(token):
        print(c(Colors.RED, "  토큰 포맷이 올바르지 않습니다 (sk-ant- prefix 아님)"))
        return False

    # 이메일 입력 (수동)
    try:
        email = input("  이메일: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    if not email or "@" not in email:
        print(c(Colors.RED, "  유효한 이메일이 필요합니다"))
        return False

    # 계정 이름
    default_name = email.split("@")[0]
    try:
        name = input(f"  계정 이름 (기본: {default_name}): ").strip() or default_name
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    # Plan 선택
    print()
    print(c(Colors.BOLD, "  Plan 선택"))
    plans = ["Free", "Pro", "Team", "Max5", "Max20"]
    for i, p in enumerate(plans, 1):
        print(f"    [{i}] {p}")
    try:
        choice = input(f"  번호 (기본: 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    plan = "Free"
    if choice:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(plans):
                plan = plans[idx]
        except ValueError:
            pass

    # 중복 토큰 검사 (저장된 long-lived credential 비교)
    index = load_index()
    for acc in index["accounts"]:
        if acc.get("tokenType") != "long-lived":
            continue
        cred_file = acc.get("credentialFile")
        if not cred_file:
            continue
        cred_path = ACCOUNTS_DIR / cred_file
        if not cred_path.exists():
            continue
        try:
            existing = json.loads(cred_path.read_text())
            if existing.get("claudeAiOauth", {}).get("accessToken") == token:
                print(c(Colors.YELLOW,
                        f"  이 토큰은 이미 등록되어 있습니다: {acc['id']} ({acc['name']})"))
                return False
        except (json.JSONDecodeError, IOError):
            continue

    # ID 생성
    account_id = generate_long_lived_account_id(email)

    # Wrap 및 저장
    wrapped = wrap_long_lived_token(token, plan)
    credential_file = f"credential_{account_id}.json"
    credential_path = ACCOUNTS_DIR / credential_file
    credential_path.write_text(json.dumps(wrapped, indent=2, ensure_ascii=False))
    os.chmod(credential_path, 0o600)

    # profile은 최소한 (oauthAccount 구조 흉내)
    profile = {
        "emailAddress": email,
        "displayName": name,
    }
    profile_file = f"profile_{account_id}.json"
    profile_path = ACCOUNTS_DIR / profile_file
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    os.chmod(profile_path, 0o600)

    # Index 등록
    now_iso = datetime.now().isoformat()
    index["accounts"].append({
        "id": account_id,
        "name": name,
        "email": email,
        "plan": plan,
        "tokenType": "long-lived",
        "tokenIssuedAt": now_iso,
        "profileFile": profile_file,
        "credentialFile": credential_file,
        "createdAt": now_iso,
    })
    save_index(index)

    expires_ms = wrapped["claudeAiOauth"]["expiresAt"]
    expires_str = datetime.fromtimestamp(expires_ms / 1000).strftime("%Y-%m-%d")

    print()
    print(c(Colors.GREEN, "  Long-lived 토큰 등록 완료"))
    print(c(Colors.DIM, "  " + "─" * 40))
    print(f"  ID: {account_id}")
    print(f"  이름: {name}")
    print(f"  이메일: {email}")
    print(f"  Plan: {plan}")
    print(f"  Type: Long-lived")
    print(f"  만료: {expires_str} (1년)")
    print()
    print(c(Colors.DIM, "  활성화: account:switch " + account_id))
    return True
```

- [ ] **Step 2: `cmd_add()` 진입 시 유형 선택**

기존 `cmd_add(name=None)` 함수의 맨 윗 줄(`current = get_current_account()` 위)에 분기 prompt 추가:

```python
def cmd_add(name=None):
    """현재 계정을 프로필로 저장 (또는 long-lived 토큰 등록)"""
    # 유형 선택
    print()
    print(c(Colors.BOLD, "  계정 등록 유형 선택"))
    print(c(Colors.DIM, "  " + "─" * 40))
    print(f"  [1] 현재 로그인된 OAuth 계정 저장 (기본)")
    print(f"  [2] Long-lived 토큰 등록 (CI/스크립트용, 1년 유효)")
    print(c(Colors.DIM, "  " + "─" * 40))
    try:
        choice = input(f"  {c(Colors.DIM, '번호 (기본: 1)')}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    if choice == "2":
        return cmd_add_long_lived()

    # === 기존 일반 OAuth 등록 로직 (변경 없음) ===
    current = get_current_account()
    # ... (이하 기존 코드 그대로)
```

- [ ] **Step 3: 수동 검증 (단위 테스트는 input 의존도가 높아 통합 테스트로 대체)**

테스트 모드 — `add_cmd.py` 정상 import 확인:

```bash
python3 -c "from claude_account_manager.commands.add_cmd import cmd_add, cmd_add_long_lived; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add claude_account_manager/commands/add_cmd.py
git commit -m "feat: /account:add에 long-lived 토큰 등록 분기 추가"
```

---

## Task 6: `commands/export_token_cmd.py` 신규

eval 가능한 export 라인을 stdout으로 출력.

**Files:**
- Create: `claude_account_manager/commands/export_token_cmd.py`
- Create: `tests/test_export_token.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_export_token.py`:

```python
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestCmdExportToken(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.accounts_dir = Path(self.tmpdir)

    def _write_credential(self, account_id, token):
        path = self.accounts_dir / f"credential_{account_id}.json"
        path.write_text(json.dumps({
            "claudeAiOauth": {"accessToken": token, "refreshToken": "",
                              "expiresAt": 9999999999999}
        }))
        return path

    def _index(self, accounts):
        return {"accounts": accounts, "activeAccountId": None}

    def test_outputs_export_line_for_long_lived(self):
        from claude_account_manager.commands import export_token_cmd
        self._write_credential("joel_token", "sk-ant-oat01-XYZ")
        with patch.object(export_token_cmd, "ACCOUNTS_DIR", self.accounts_dir), \
             patch.object(export_token_cmd, "load_index", return_value=self._index([
                 {"id": "joel_token", "name": "joel", "tokenType": "long-lived",
                  "credentialFile": "credential_joel_token.json"}
             ])):
            captured = io.StringIO()
            with patch.object(sys, "stdout", captured):
                rc = export_token_cmd.cmd_export_token("joel_token")
            self.assertTrue(rc)
            self.assertIn("export CLAUDE_CODE_OAUTH_TOKEN=", captured.getvalue())
            self.assertIn("sk-ant-oat01-XYZ", captured.getvalue())

    def test_returns_false_on_missing_account(self):
        from claude_account_manager.commands import export_token_cmd
        with patch.object(export_token_cmd, "load_index",
                          return_value=self._index([])):
            self.assertFalse(export_token_cmd.cmd_export_token("nope"))

    def test_export_line_uses_single_quotes_for_safety(self):
        from claude_account_manager.commands import export_token_cmd
        self._write_credential("joel_token", "sk-ant-oat01-Has$pecial")
        with patch.object(export_token_cmd, "ACCOUNTS_DIR", self.accounts_dir), \
             patch.object(export_token_cmd, "load_index", return_value=self._index([
                 {"id": "joel_token", "name": "joel", "tokenType": "long-lived",
                  "credentialFile": "credential_joel_token.json"}
             ])):
            captured = io.StringIO()
            with patch.object(sys, "stdout", captured):
                export_token_cmd.cmd_export_token("joel_token")
            # token must be single-quoted so $ is not interpreted
            self.assertIn("export CLAUDE_CODE_OAUTH_TOKEN='sk-ant-oat01-Has$pecial'",
                          captured.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m unittest tests.test_export_token -v
```

Expected: `ModuleNotFoundError: claude_account_manager.commands.export_token_cmd`

- [ ] **Step 3: 구현**

`claude_account_manager/commands/export_token_cmd.py`:

```python
"""
cmd_export_token: 계정의 토큰을 eval 가능한 export 라인으로 stdout 출력

usage:
    eval $(python3 -m claude_account_manager export-token <id>)
또는 shell function wrapper(account:export-token)에서 자동 eval.
"""
import json
import sys

from ..config import ACCOUNTS_DIR
from ..storage import load_index
from ..ui import c, Colors
from ..long_lived import is_long_lived_account, format_expiry_dday


def cmd_export_token(account_id):
    """해당 계정의 access token을 export 라인으로 stdout 출력

    long-lived와 일반 OAuth 둘 다 동작. stderr에 만료/경고 정보 출력.
    """
    if not account_id:
        print("사용법: account export-token <id>", file=sys.stderr)
        return False

    index = load_index()
    account = None
    for acc in index["accounts"]:
        if acc["id"] == account_id:
            account = acc
            break

    if not account:
        print(f"계정을 찾을 수 없습니다: {account_id}", file=sys.stderr)
        return False

    cred_file = account.get("credentialFile")
    if not cred_file:
        print(f"credential 파일이 없습니다: {account_id}", file=sys.stderr)
        return False

    cred_path = ACCOUNTS_DIR / cred_file
    if not cred_path.exists():
        print(f"credential 파일이 존재하지 않습니다: {cred_path}", file=sys.stderr)
        return False

    try:
        credential = json.loads(cred_path.read_text())
    except (json.JSONDecodeError, IOError) as e:
        print(f"credential 파싱 실패: {e}", file=sys.stderr)
        return False

    token = credential.get("claudeAiOauth", {}).get("accessToken")
    if not token:
        print(f"토큰이 없습니다: {account_id}", file=sys.stderr)
        return False

    # stderr 경고
    if is_long_lived_account(account):
        expires_ms = credential.get("claudeAiOauth", {}).get("expiresAt")
        label, severity = format_expiry_dday(expires_ms)
        if severity == "expired":
            print(f"[warning] long-lived 토큰 만료됨 ({account['name']})", file=sys.stderr)
        elif severity == "danger":
            print(f"[warning] long-lived 토큰 만료 임박 ({label}, {account['name']})",
                  file=sys.stderr)
    else:
        print(f"[info] 일반 OAuth 토큰은 약 8시간 후 만료됩니다 ({account['name']})",
              file=sys.stderr)

    # stdout: shell-evalable export line. 토큰은 single-quote로 감싸 $ 등 안전.
    # 안에 single quote가 있을 경우 깨질 수 있지만 OAuth 토큰은 base64-safe라 OK.
    print(f"export CLAUDE_CODE_OAUTH_TOKEN='{token}'")
    return True
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m unittest tests.test_export_token -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add claude_account_manager/commands/export_token_cmd.py tests/test_export_token.py
git commit -m "feat: account export-token 명령 추가"
```

---

## Task 7: `commands/__init__.py`에 서브커맨드 등록

**Files:**
- Modify: `claude_account_manager/commands/__init__.py`

- [ ] **Step 1: import + dispatch 추가**

상단 import 블록에 추가:

```python
from .export_token_cmd import cmd_export_token
```

`main()` 함수의 명령 분기에서 `elif args[0] == "current":` 위에 추가:

```python
    elif args[0] == "export-token":
        account_id = args[1] if len(args) > 1 else None
        cmd_export_token(account_id)
```

`__all__` 끝에 추가:

```python
    "cmd_export_token",
```

- [ ] **Step 2: 검증**

```bash
python3 -m claude_account_manager export-token 2>&1 | head -5
```

Expected: `사용법: account export-token <id>` (인자 없음 에러)

```bash
python3 -m claude_account_manager export-token nonexistent 2>&1 | head -5
```

Expected: `계정을 찾을 수 없습니다: nonexistent`

- [ ] **Step 3: Commit**

```bash
git add claude_account_manager/commands/__init__.py
git commit -m "feat: export-token CLI 서브커맨드 등록"
```

---

## Task 8: `switch_cmd.py` `--shell-export` 플래그 + tokenType 분기

기존 `cmd_switch`는 keychain만 다룸. `--shell-export` 추가 시 stdout에 export/unset 라인 출력.

**Files:**
- Modify: `claude_account_manager/commands/switch_cmd.py`
- Modify: `claude_account_manager/commands/__init__.py`
- Create: `tests/test_switch_long_lived.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_switch_long_lived.py`:

```python
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestSwitchShellExport(unittest.TestCase):
    """`--shell-export` 플래그가 켜졌을 때 stdout에 export/unset 라인이 나오는지 확인.

    cmd_switch 전체는 통합 의존도가 높아 핵심 단위는 별도 헬퍼로 분리한다.
    여기서는 build_shell_export_lines 헬퍼를 검증.
    """

    def test_long_lived_emits_export_line(self):
        from claude_account_manager.commands.switch_cmd import build_shell_export_lines
        line = build_shell_export_lines(token_type="long-lived",
                                        access_token="sk-ant-oat01-XYZ")
        self.assertEqual(line, "export CLAUDE_CODE_OAUTH_TOKEN='sk-ant-oat01-XYZ'")

    def test_oauth_emits_unset_line(self):
        from claude_account_manager.commands.switch_cmd import build_shell_export_lines
        line = build_shell_export_lines(token_type="oauth", access_token="ignored")
        self.assertEqual(line, "unset CLAUDE_CODE_OAUTH_TOKEN")

    def test_oauth_default_when_missing(self):
        from claude_account_manager.commands.switch_cmd import build_shell_export_lines
        line = build_shell_export_lines(token_type=None, access_token=None)
        self.assertEqual(line, "unset CLAUDE_CODE_OAUTH_TOKEN")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m unittest tests.test_switch_long_lived -v
```

Expected: `ImportError: cannot import name 'build_shell_export_lines'`

- [ ] **Step 3: 헬퍼 함수 추가**

`claude_account_manager/commands/switch_cmd.py` 상단 import에 추가:

```python
from ..long_lived import is_long_lived_account, format_expiry_dday
```

파일 상단(`_cleanup_old_backups` 위)에 추가:

```python
def build_shell_export_lines(token_type, access_token):
    """switch 결과로 emit할 shell line 생성

    - long-lived: export CLAUDE_CODE_OAUTH_TOKEN='...'
    - oauth/None: unset CLAUDE_CODE_OAUTH_TOKEN
    """
    if token_type == "long-lived" and access_token:
        return f"export CLAUDE_CODE_OAUTH_TOKEN='{access_token}'"
    return "unset CLAUDE_CODE_OAUTH_TOKEN"
```

- [ ] **Step 4: `cmd_switch` 시그니처 변경 + long-lived 분기**

`cmd_switch(account_id=None)` → `cmd_switch(account_id=None, shell_export=False)`

함수 내 마지막 print 직전(`print(c(Colors.YELLOW, "  Claude Code를 재시작해야..."))` 위)에 추가:

```python
    # Long-lived 토큰 만료 D-day 표시
    if is_long_lived_account(account):
        expires_ms = None
        try:
            credential = json.loads((ACCOUNTS_DIR / credential_file).read_text())
            expires_ms = credential.get("claudeAiOauth", {}).get("expiresAt")
        except Exception:
            pass
        if expires_ms:
            label, severity = format_expiry_dday(expires_ms)
            color = {"danger": Colors.RED, "warn": Colors.YELLOW,
                     "expired": Colors.RED}.get(severity, Colors.DIM)
            print(f"  Type: {c(Colors.CYAN, 'Long-lived')} (만료: {c(color, label)})")

    # --shell-export 모드: stdout에 eval 가능한 라인 추가
    if shell_export:
        token_type = account.get("tokenType", "oauth")
        access_token = None
        if token_type == "long-lived":
            try:
                credential = json.loads((ACCOUNTS_DIR / credential_file).read_text())
                access_token = credential.get("claudeAiOauth", {}).get("accessToken")
            except Exception:
                pass
        print(build_shell_export_lines(token_type, access_token))
```

**참고:** Long-lived 계정은 기존 refresh 로직(`_safe_refresh_credential`)을 호출하면 refreshToken이 빈 값이라 실패한다. switch_cmd 안에서 long-lived는 refresh 건너뛰는 분기도 함께 추가.

기존 `if credential_file:` 블록 안의 `new_credential, error = _safe_refresh_credential(...)` 호출을 다음과 같이 감싼다:

```python
            if is_long_lived_account(account):
                # long-lived는 refresh 안 함 — 파일 그대로 사용
                try:
                    new_credential = json.loads(credential_path.read_text())
                    token_status = "fresh"
                except (json.JSONDecodeError, IOError):
                    new_credential = None
                    token_status = "no_credential"
                error = None
            else:
                new_credential, error = _safe_refresh_credential(credential_path, account['id'], skip_fresh_check=True)
                # 이하 기존 로직 (token_status 분기 등)
```

(기존 if/elif 분기들이 이 들여쓰기 안으로 이동. 코드 전체 흐름은 변경 없음.)

- [ ] **Step 5: dispatcher 업데이트**

`claude_account_manager/commands/__init__.py`의 switch 분기:

```python
    elif args[0] == "switch":
        # --shell-export 플래그 파싱
        rest = args[1:]
        shell_export = False
        positional = []
        for arg in rest:
            if arg == "--shell-export":
                shell_export = True
            else:
                positional.append(arg)
        account_id = positional[0] if positional else None
        cmd_switch(account_id, shell_export=shell_export)
```

- [ ] **Step 6: 단위 테스트 통과 확인**

```bash
python3 -m unittest tests.test_switch_long_lived -v
```

Expected: 3 passed

- [ ] **Step 7: 통합 import 확인**

```bash
python3 -c "from claude_account_manager.commands.switch_cmd import cmd_switch, build_shell_export_lines; print('OK')"
python3 -m claude_account_manager switch --shell-export 2>&1 | head -3
```

Expected: 첫 줄 `OK`. 두 번째는 `등록된 계정이 없습니다` 또는 계정 선택 prompt (정상).

- [ ] **Step 8: Commit**

```bash
git add claude_account_manager/commands/switch_cmd.py claude_account_manager/commands/__init__.py tests/test_switch_long_lived.py
git commit -m "feat: switch에 --shell-export 플래그 + long-lived 분기 추가"
```

---

## Task 9: `token_cmd.py` long-lived skip (check + refresh-all)

자동 refresh + check가 long-lived 계정을 건드리지 않도록.

**Files:**
- Modify: `claude_account_manager/commands/token_cmd.py`
- Create: `tests/test_refresh_skip_long_lived.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_refresh_skip_long_lived.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestRefreshAllSkipsLongLived(unittest.TestCase):
    def test_refresh_all_skips_long_lived_accounts(self):
        from claude_account_manager.commands import token_cmd

        accounts = [
            {"id": "joel", "name": "joel", "credentialFile": "credential_joel.json"},  # oauth (default)
            {"id": "joel_token", "name": "joel-ci", "tokenType": "long-lived",
             "credentialFile": "credential_joel_token.json"},
        ]
        index = {"accounts": accounts, "activeAccountId": "joel"}

        refresh_calls = []

        def fake_refresh(credential_path, account_id, **kw):
            refresh_calls.append(account_id)
            return ({"claudeAiOauth": {"accessToken": "x", "refreshToken": "y",
                                       "expiresAt": 1}}, None)

        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "credential_joel.json").write_text("{}")
        (tmpdir / "credential_joel_token.json").write_text("{}")

        with patch.object(token_cmd, "load_index", return_value=index), \
             patch.object(token_cmd, "ACCOUNTS_DIR", tmpdir), \
             patch.object(token_cmd, "_safe_refresh_credential", side_effect=fake_refresh):
            count = token_cmd.cmd_refresh_all()

        self.assertEqual(refresh_calls, ["joel"])
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m unittest tests.test_refresh_skip_long_lived -v
```

Expected: 테스트 실패 (long-lived 계정도 refresh 시도되어 refresh_calls가 2개)

(혹은 token_cmd 구조에 따라 다른 형태 실패. 어느 쪽이든 통과 안 함이 핵심.)

- [ ] **Step 3: 구현**

`claude_account_manager/commands/token_cmd.py` 상단에 추가:

```python
from ..long_lived import is_long_lived_account, format_expiry_dday
```

`cmd_refresh_all()` 함수 안의 account 순회 부분 시작 부분에서 long-lived skip 분기 추가:

```python
def cmd_refresh_all():
    """모든 계정의 토큰 갱신 (long-lived는 skip)"""
    index = load_index()
    count = 0
    for acc in index["accounts"]:
        if is_long_lived_account(acc):
            # long-lived는 refresh 안 함 (refresh token 없음)
            continue
        # ... (이하 기존 refresh 호출 코드)
```

`cmd_refresh_expiring(hours)`도 동일하게 skip:

```python
def cmd_refresh_expiring(hours=1):
    index = load_index()
    count = 0
    for acc in index["accounts"]:
        if is_long_lived_account(acc):
            continue
        # ... (기존 코드)
```

`cmd_check()`도 long-lived 분기 추가 — 자세히는 token_cmd.py 본문 확인 후 다음을 삽입:

`cmd_check()` 본문 내, 활성 계정 정보를 가져온 직후 (또는 keychain credential을 가져온 직후) long-lived 분기:

```python
def cmd_check():
    """OAuth 토큰 상태 확인 (long-lived 계정은 expiresAt만 검사)"""
    index = load_index()
    active_id = index.get("activeAccountId")
    active_account = next((a for a in index["accounts"] if a["id"] == active_id), None)

    if active_account and is_long_lived_account(active_account):
        # long-lived: API 호출 없이 expiresAt만 검사
        cred_file = active_account.get("credentialFile")
        if not cred_file:
            print(c(Colors.RED, "  credential 파일이 없습니다"))
            return
        cred_path = ACCOUNTS_DIR / cred_file
        try:
            credential = json.loads(cred_path.read_text())
        except (json.JSONDecodeError, IOError) as e:
            print(c(Colors.RED, f"  credential 파싱 실패: {e}"))
            return
        expires_ms = credential.get("claudeAiOauth", {}).get("expiresAt")
        label, severity = format_expiry_dday(expires_ms)
        color = {"normal": Colors.GREEN, "warn": Colors.YELLOW,
                 "danger": Colors.RED, "expired": Colors.RED}.get(severity, Colors.DIM)
        print()
        print(c(Colors.BOLD, f"  Long-lived 토큰: {active_account['name']}"))
        print(f"  만료까지: {c(color, label)}")
        if severity == "expired":
            print(c(Colors.RED, "  → 재발급 필요: claude setup-token → /account:add"))
        return

    # === 기존 일반 OAuth check 로직 (변경 없음) ===
    # ... (이하 기존 코드)
```

(token_cmd.py에 이미 import된 `json`, `ACCOUNTS_DIR`, `c`, `Colors` 활용. 누락 시 import 추가.)

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m unittest tests.test_refresh_skip_long_lived -v
```

Expected: passed

- [ ] **Step 5: Commit**

```bash
git add claude_account_manager/commands/token_cmd.py tests/test_refresh_skip_long_lived.py
git commit -m "feat: refresh-all / check가 long-lived 계정 skip하도록 분기"
```

---

## Task 10: `list_cmd.py` Type 컬럼 + long-lived usage skip + D-day 표시

**Files:**
- Modify: `claude_account_manager/commands/list_cmd.py`

- [ ] **Step 1: list_cmd 구조 확인**

```bash
python3 -c "import inspect; from claude_account_manager.commands.list_cmd import cmd_list; print(inspect.getsourcefile(cmd_list))"
head -40 claude_account_manager/commands/list_cmd.py
```

목적: 계정 순회 부분과 사용량 조회 위치 파악.

- [ ] **Step 2: 분기 추가**

`claude_account_manager/commands/list_cmd.py` 상단 import에 추가:

```python
from ..long_lived import is_long_lived_account, format_expiry_dday
```

계정 순회 부분에서 (각 acc 처리 루프 안), 사용량 fetch 호출 직전에 long-lived 분기 추가:

```python
        # long-lived 계정: usage 조회 skip + D-day 만 표시
        if is_long_lived_account(acc):
            cred_file = acc.get("credentialFile")
            expires_ms = None
            if cred_file:
                cred_path = ACCOUNTS_DIR / cred_file
                if cred_path.exists():
                    try:
                        cred = json.loads(cred_path.read_text())
                        expires_ms = cred.get("claudeAiOauth", {}).get("expiresAt")
                    except (json.JSONDecodeError, IOError):
                        pass
            label, severity = format_expiry_dday(expires_ms)
            color = {"normal": Colors.DIM, "warn": Colors.YELLOW,
                     "danger": Colors.RED, "expired": Colors.RED}.get(severity, Colors.DIM)
            type_badge = c(Colors.CYAN, "[Long-lived]")
            print(f"      {type_badge} 만료: {c(color, label)}")
            continue  # usage 조회 스킵, 다음 계정으로
```

각 계정의 명령 prefix 옆에 Type 배지를 추가하기 위해, plan_badge 옆에 type 표시 추가:

```python
        if is_long_lived_account(acc):
            type_indicator = c(Colors.CYAN, " [CI]")
        else:
            type_indicator = ""
        print(f"  [{i}] {marker} {acc['name']}{org_badge} {plan_badge}{type_indicator}")
```

(list_cmd.py 본문의 정확한 위치는 코드를 보고 결정. 핵심은 long-lived 분기로 인해 fetch_usage 호출이 안 일어나도록.)

- [ ] **Step 3: 수동 검증**

```bash
python3 -m claude_account_manager list
```

Expected: 등록된 계정 목록. 등록 단계에서 long-lived 계정이 있다면 `[CI]` 배지 + D-day 표시.

- [ ] **Step 4: Commit**

```bash
git add claude_account_manager/commands/list_cmd.py
git commit -m "feat: list에 Long-lived Type 배지 + D-day 표시"
```

---

## Task 11: SessionStart hook — function wrapper 주입 + 만료 경고

**Files:**
- Modify: `hooks-handlers/session-start.sh`
- Modify: `claude_account_manager/commands/__init__.py` (만료 경고용 서브커맨드 추가)

- [ ] **Step 1: 만료 경고 서브커맨드 신설**

`claude_account_manager/commands/misc_cmd.py` 끝에 추가:

```python
def cmd_warn_expiring_long_lived(days=7):
    """long-lived 계정 중 만료 임박(D-days 이내) 항목을 stderr로 경고"""
    import sys
    import json
    from ..config import ACCOUNTS_DIR
    from ..storage import load_index
    from ..long_lived import is_long_lived_account, format_expiry_dday

    index = load_index()
    for acc in index["accounts"]:
        if not is_long_lived_account(acc):
            continue
        cred_file = acc.get("credentialFile")
        if not cred_file:
            continue
        cred_path = ACCOUNTS_DIR / cred_file
        if not cred_path.exists():
            continue
        try:
            cred = json.loads(cred_path.read_text())
        except (json.JSONDecodeError, IOError):
            continue
        expires_ms = cred.get("claudeAiOauth", {}).get("expiresAt")
        label, severity = format_expiry_dday(expires_ms)
        if severity in ("danger", "expired"):
            print(f"[warning] long-lived 토큰 '{acc['name']}' {label}. "
                  f"갱신: claude setup-token → /account:add", file=sys.stderr)
```

`claude_account_manager/commands/__init__.py`의 misc import 줄 끝에 `cmd_warn_expiring_long_lived` 추가:

```python
from .misc_cmd import (
    cmd_current, cmd_rename, cmd_set_plan, cmd_setup_hook,
    cmd_update, cmd_version, cmd_help, cmd_warn_expiring_long_lived,
)
```

`main()`의 `elif args[0] == "refresh-expiring":` 아래에 추가:

```python
    elif args[0] == "warn-expiring-long-lived":
        cmd_warn_expiring_long_lived()
        sys.exit(0)
```

- [ ] **Step 2: SessionStart hook에 호출 추가**

`hooks-handlers/session-start.sh`의 `python3 "$SCRIPT_DIR/account_manager.py" auto-add 2>>...` 줄 아래에 추가:

```bash
python3 "$SCRIPT_DIR/account_manager.py" warn-expiring-long-lived 2>>"$LOG_DIR/token-refresh.log" || true
```

- [ ] **Step 3: 검증**

```bash
python3 -m claude_account_manager warn-expiring-long-lived
```

Expected: 만료 임박 long-lived 계정 없으면 출력 없음.

- [ ] **Step 4: Commit**

```bash
git add claude_account_manager/commands/misc_cmd.py claude_account_manager/commands/__init__.py hooks-handlers/session-start.sh
git commit -m "feat: SessionStart에 long-lived 만료 임박 경고 추가"
```

---

## Task 12: Shell function wrapper (eval 자동화)

`hooks-handlers/session-start.sh`의 alias 블록에 function 두 개 추가.

**Files:**
- Modify: `hooks-handlers/session-start.sh`

- [ ] **Step 1: function wrapper 정의**

`hooks-handlers/session-start.sh`의 `write_v2_block` 함수 본문에서 `account:switch` 정의 부분을 다음으로 교체 (마커 블록 안):

```bash
# account:switch — long-lived 토큰일 경우 자동 env export
account:switch() {
    local output
    output=$(python3 -m claude_account_manager switch --shell-export "$@")
    local rc=$?
    # eval 가능한 export/unset 라인만 분리하여 적용
    while IFS= read -r line; do
        case "$line" in
            export\ CLAUDE_CODE_OAUTH_TOKEN=*|unset\ CLAUDE_CODE_OAUTH_TOKEN*)
                eval "$line"
                ;;
            *)
                printf '%s\n' "$line"
                ;;
        esac
    done <<< "$output"
    return $rc
}

# account:export-token — 토큰을 자동 env export
account:export-token() {
    local output
    output=$(python3 -m claude_account_manager export-token "$@")
    local rc=$?
    while IFS= read -r line; do
        case "$line" in
            export\ CLAUDE_CODE_OAUTH_TOKEN=*)
                eval "$line"
                echo "  CLAUDE_CODE_OAUTH_TOKEN 환경변수 설정됨"
                ;;
            *)
                printf '%s\n' "$line"
                ;;
        esac
    done <<< "$output"
    return $rc
}
```

(기존 `account:switch` 정의가 있으면 그것을 교체. 다른 function 정의들과 동일한 블록 안에 위치.)

block version tag도 v3로 올림: `BLOCK_VERSION_TAG="# account-manager-block: v3"`

- [ ] **Step 2: 수동 검증**

```bash
bash hooks-handlers/session-start.sh
grep -A 5 "^account:switch" ~/.zshrc | head -20
```

Expected: function 정의가 마커 블록 안에 존재.

```zsh
# 새 zsh 세션 열어서:
type account:switch
account:export-token --help 2>&1 | head -3
```

Expected: function (not alias). 두 번째는 사용법 안내.

- [ ] **Step 3: Commit**

```bash
git add hooks-handlers/session-start.sh
git commit -m "feat: account:switch/account:export-token zsh function wrapper 추가"
```

---

## Task 13: SKILL.md + README 업데이트

**Files:**
- Modify: `skills/account-add/SKILL.md`
- Modify: `skills/account-switch/SKILL.md`
- Modify: `skills/account-list/SKILL.md`
- Create: `skills/account-export-token/SKILL.md`
- Modify: `README.md`
- Modify: `README.ko.md`

- [ ] **Step 1: account-add/SKILL.md 업데이트**

본문 시작 또는 적절한 위치에 한 줄 추가:

```markdown
- `/account:add` 진입 시 "현재 OAuth 계정 저장" 또는 "Long-lived 토큰 등록" 중 선택.
  Long-lived는 `claude setup-token` 발급 토큰을 paste 입력으로 등록 (CI/스크립트용).
```

- [ ] **Step 2: account-switch/SKILL.md 업데이트**

추가:

```markdown
- Long-lived 토큰 계정으로 switch 시 `CLAUDE_CODE_OAUTH_TOKEN` 환경변수도 자동 export됨
  (.zshrc의 account:switch function wrapper가 처리).
```

- [ ] **Step 3: account-list/SKILL.md 업데이트**

추가:

```markdown
- Long-lived 계정은 `[CI]` 배지와 D-day 만료 시각으로 표시. 사용량 API 호출은 skip.
```

- [ ] **Step 4: account-export-token/SKILL.md 신설**

`skills/account-export-token/SKILL.md`:

```markdown
---
description: Export account token to CLAUDE_CODE_OAUTH_TOKEN env. Triggered by "export token", "env token", "CI 토큰".
allowed-tools: Bash
argument-hint: "<account-id>"
---

# /account:export-token

해당 계정의 access token을 `CLAUDE_CODE_OAUTH_TOKEN` 환경변수로 export.

## 사용 예시

```bash
/account:export-token joel_token
# → 현재 shell에 환경변수 set됨 (account:export-token function wrapper 사용 시)
```

## Long-lived vs OAuth

- Long-lived 토큰: 1년 유효, refresh 불필요
- 일반 OAuth: 약 8시간 후 만료. 그 시점엔 다시 export 필요.

## 사용 흐름

```bash
$ /account:add               # → [2] Long-lived 토큰 등록
$ /account:export-token <id>  # → env 설정 후 스크립트 실행
$ npm run build              # CLAUDE_CODE_OAUTH_TOKEN 으로 인증
```
```

- [ ] **Step 5: README.md + README.ko.md 업데이트**

기존 README에 `## Long-lived OAuth Token (CI/Script 용)` 섹션 추가 (한국어판 README.ko.md에도 동일 구조):

```markdown
## Long-lived OAuth Token (CI/Script 용)

`claude setup-token`이 발급하는 1년 유효 토큰을 등록·관리할 수 있다.

### 발급 + 등록
```bash
claude setup-token                # OAuth 후 토큰 출력
# 토큰 복사 후
/account:add                       # → [2] Long-lived 토큰 등록 선택 → paste
```

### 활성화
```bash
/account:switch <id>               # function wrapper가 env 자동 export
# 또는 명시적으로:
/account:export-token <id>
```

### 주의사항
- Long-lived는 refresh token이 없어 1년 후 재발급 필요
- inference-only scope (Remote Control 등 일부 기능 제한)
- bare mode(`claude --bare`)에서는 `ANTHROPIC_API_KEY` 필요 — 본 토큰 미지원
```

- [ ] **Step 6: Commit**

```bash
git add skills/ README.md README.ko.md
git commit -m "docs: long-lived 토큰 관련 SKILL.md / README 업데이트"
```

---

## Task 14: 통합 시나리오 수동 검증

각 시나리오를 실제 환경에서 검증하고 결과 기록.

**Files:**
- Modify: `docs/superpowers/specs/2026-05-13-long-lived-token-design.md` (검증 결과 추가)

- [ ] **Step 1: 시나리오 1 — 등록 + switch + 사용**

```bash
# 1. 토큰 발급
claude setup-token  # 발급된 토큰 복사

# 2. 등록
python3 -m claude_account_manager add
# → [2] 선택, 토큰 paste, email/name/plan 입력

# 3. list로 표시 확인
python3 -m claude_account_manager list
# Expected: [CI] 배지 + D-365 표시

# 4. switch
account:switch <new_id>
# Expected: keychain 교체 + CLAUDE_CODE_OAUTH_TOKEN export

echo $CLAUDE_CODE_OAUTH_TOKEN  # 환경변수 확인

# 5. claude 기동
claude --print "say hello"
# Expected: 정상 응답 (POC A1 통과 케이스)
```

- [ ] **Step 2: 시나리오 2 — long-lived ↔ 일반 OAuth 왕복**

```bash
# 일반 OAuth로 switch
account:switch joel
echo $CLAUDE_CODE_OAUTH_TOKEN  # Expected: empty

# long-lived로 switch
account:switch joel_token
echo $CLAUDE_CODE_OAUTH_TOKEN  # Expected: set

# 일반 OAuth로 복귀
account:switch joel
echo $CLAUDE_CODE_OAUTH_TOKEN  # Expected: empty (unset)
```

- [ ] **Step 3: 시나리오 3 — refresh hook skip 확인**

```bash
# SessionStart hook 트리거 (또는 직접):
python3 -m claude_account_manager refresh-all
# Expected: long-lived 계정은 건드리지 않음 (로그에서 확인)
tail -20 ~/.claude/accounts/logs/token-refresh.log
```

- [ ] **Step 4: 시나리오 4 — check 명령**

```bash
# long-lived 계정 활성 상태에서:
account:switch joel_token
python3 -m claude_account_manager check
# Expected: "Long-lived 토큰: ... 만료까지: D-364" (API 호출 없음)
```

- [ ] **Step 5: 결과 기록**

`docs/superpowers/specs/2026-05-13-long-lived-token-design.md` Section 11에 추가:

```markdown
## 통합 검증 결과 (YYYY-MM-DD)

| 시나리오 | 결과 |
|---|---|
| 등록 + switch + claude 기동 | PASS / FAIL |
| OAuth ↔ long-lived 왕복 | PASS / FAIL |
| refresh hook skip | PASS / FAIL |
| check 명령 long-lived 분기 | PASS / FAIL |
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-05-13-long-lived-token-design.md
git commit -m "docs: long-lived 통합 시나리오 검증 결과 기록"
```

---

## Task 15: 릴리즈 (Phase 1+2+3 완료 후)

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 버전 bump**

`/account:release` skill 호출 또는 수동:

```bash
# plugin.json version 2.2.0 → 2.3.0 (minor bump)
```

- [ ] **Step 2: CHANGELOG 항목 추가**

```markdown
## [2.3.0] - YYYY-MM-DD
### Added
- Long-lived OAuth token (`claude setup-token` 발급) 등록·관리 지원
- `/account:export-token` 명령 신설
- `account:switch` zsh function wrapper가 `CLAUDE_CODE_OAUTH_TOKEN` env 자동 처리
- SessionStart hook에 long-lived 만료 임박(D-7) 경고
```

- [ ] **Step 3: Release**

CLAUDE.md 규칙대로 `/account:release` skill 호출.

---

## 자체 점검 (writing-plans self-review)

### Spec coverage
- ✅ Section 3 결정사항(완전 통합/Hybrid/통합 UX/eval wrapper) → Task 5/8/12에 매핑
- ✅ Section 4 데이터 모델 → Task 2 (wrap), Task 5 (index entry), Task 4 (id)
- ✅ Section 5 명령 흐름 → Task 5(add) / 6(export-token) / 8(switch) / 9(check) / 10(list) / 11(hook) / 12(wrapper)
- ✅ Section 6 에러 처리 → Task 5/6/8에서 각각 처리
- ✅ Section 7 구현 단위 → Task 1-13 매핑
- ✅ Section 8 POC → Task 0
- ✅ Section 9 단계적 출시 → Task 분리에 반영 (1-7 MVP, 8-11 통합, 12-14 폴리시)
- ✅ Section 10 롤백 → tokenType backward compat은 Task 3에서 보장

### Placeholder scan
- POC `<TOKEN>` 같은 사용자 입력 표시 — 의도적, 명시적 / 코드 내 placeholder 없음

### Type consistency
- `is_long_lived_account(account_entry)` 시그니처 일관됨 (전 task)
- `format_expiry_dday(expires_at_ms)` 반환 `(label, severity)` 일관됨
- `wrap_long_lived_token(token, plan, validity_days=...)` 인자 일관
- `build_shell_export_lines(token_type, access_token)` 일관

---

**Plan 완료.** 저장 경로: `docs/superpowers/plans/2026-05-13-long-lived-token.md`
