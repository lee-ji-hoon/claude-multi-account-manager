# multi-login-codex Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Codex CLI용 다중 계정 관리 플러그인을 새 레포 `multi-login-codex`로 구현한다.

**Architecture:** `multi-login-claude`의 Python 패키지 구조를 Codex 환경에 맞게 포팅. macOS Keychain 대신 `~/.codex/auth.json` 파일 기반 자격증명, OAuth 갱신 엔드포인트는 `https://auth.openai.com/oauth/token`. `hooks.json` 주입 방식으로 SessionStart/UserPromptSubmit 훅 연동.

**Tech Stack:** Python 3 (표준 라이브러리만), oh-my-codex skills, Bash hooks

---

## 레퍼런스

- 참조 레포: `/Users/ezhoon/Desktop/ai-project/multi-login-claude/`
- 새 레포 위치: `/Users/ezhoon/Desktop/ai-project/multi-login-codex/`
- Codex 설정 홈: `~/.codex/`
- OAuth client_id: `app_EMoamEEZ73f0CkXaXp7hrann`
- 토큰 유효기간: 240시간 (10일)
- 갱신 엔드포인트: `https://auth.openai.com/oauth/token`
- refresh_token: **1회용** — 갱신 즉시 새 토큰을 파일에 저장해야 함

---

## 파일 구조

```
multi-login-codex/
├── account_manager.py
├── codex_account_manager/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── auth.py              # auth.json 읽기/쓰기 (keychain.py 역할)
│   ├── token.py             # OAuth 토큰 갱신
│   ├── storage.py           # index.json I/O
│   ├── api.py               # OpenAI API 사용량 조회
│   ├── logger.py
│   ├── ui.py
│   ├── account.py
│   └── commands/
│       ├── __init__.py
│       ├── list_cmd.py
│       ├── add_cmd.py
│       ├── switch_cmd.py
│       ├── remove_cmd.py
│       └── token_cmd.py
├── hooks-handlers/
│   ├── session-start.sh
│   └── prompt-submit.sh
├── skills/
│   ├── list/SKILL.md
│   ├── add/SKILL.md
│   ├── switch/SKILL.md
│   ├── remove/SKILL.md
│   └── check/SKILL.md
├── install.sh
├── tests/
│   ├── test_auth.py
│   ├── test_token.py
│   └── test_storage.py
└── .codex-plugin/
    └── plugin.json
```

---

## Task 1: 레포 초기화 및 패키지 골격

**Files:**
- Create: `multi-login-codex/` (새 디렉토리)
- Create: `account_manager.py`
- Create: `codex_account_manager/__init__.py`
- Create: `codex_account_manager/__main__.py`
- Create: `.codex-plugin/plugin.json`

- [ ] **Step 1: 레포 디렉토리 생성 및 git 초기화**

```bash
mkdir -p /Users/ezhoon/Desktop/ai-project/multi-login-codex
cd /Users/ezhoon/Desktop/ai-project/multi-login-codex
git init
```

- [ ] **Step 2: `.gitignore` 작성**

```
__pycache__/
*.pyc
*.pyo
.DS_Store
tests/__pycache__/
```

- [ ] **Step 3: `account_manager.py` 작성**

```python
#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from codex_account_manager import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: `codex_account_manager/__init__.py` 작성**

```python
def main():
    from .commands import dispatch
    dispatch()
```

- [ ] **Step 5: `codex_account_manager/__main__.py` 작성**

```python
from codex_account_manager import main
main()
```

- [ ] **Step 6: `.codex-plugin/plugin.json` 작성**

```json
{
  "name": "account",
  "description": "Codex CLI multi-account manager - switch accounts, auto-refresh tokens",
  "version": "1.0.0",
  "author": { "name": "ezhoon" },
  "repository": "https://github.com/lee-ji-hoon/multi-login-codex",
  "keywords": ["account", "multi-account", "oauth", "switch"],
  "skills": "./skills/"
}
```

- [ ] **Step 7: 커밋**

```bash
git add .
git commit -m "chore: 레포 초기화 및 패키지 골격"
```

---

## Task 2: `config.py` — 경로 상수 및 설정값

**Files:**
- Create: `codex_account_manager/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_config.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pathlib import Path
from codex_account_manager.config import (
    CODEX_DIR, CODEX_AUTH_FILE, ACCOUNTS_DIR, INDEX_FILE,
    TOKEN_VALIDITY_HOURS, TOKEN_FRESH_THRESHOLD_HOURS,
    OAUTH_CLIENT_ID, OAUTH_TOKEN_URL,
)

def test_paths_are_absolute():
    assert CODEX_DIR.is_absolute()
    assert CODEX_AUTH_FILE.is_absolute()
    assert ACCOUNTS_DIR.is_absolute()
    assert INDEX_FILE.is_absolute()

def test_constants():
    assert TOKEN_VALIDITY_HOURS == 240
    assert TOKEN_FRESH_THRESHOLD_HOURS == 230
    assert OAUTH_CLIENT_ID == "app_EMoamEEZ73f0CkXaXp7hrann"
    assert "auth.openai.com" in OAUTH_TOKEN_URL
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd /Users/ezhoon/Desktop/ai-project/multi-login-codex
python3 -m pytest tests/test_config.py -v
```
Expected: `ModuleNotFoundError: No module named 'codex_account_manager.config'`

- [ ] **Step 3: `config.py` 작성**

```python
"""Configuration constants and paths for Codex Account Manager"""
import json
from pathlib import Path


def _get_version():
    try:
        plugin_json = Path(__file__).parent.parent / ".codex-plugin" / "plugin.json"
        if plugin_json.exists():
            return json.loads(plugin_json.read_text()).get("version", "0.0.0")
    except Exception:
        pass
    return "0.0.0"


__version__ = _get_version()

# Codex 경로
CODEX_DIR = Path.home() / ".codex"
CODEX_AUTH_FILE = CODEX_DIR / "auth.json"
ACCOUNTS_DIR = CODEX_DIR / "accounts"
INDEX_FILE = ACCOUNTS_DIR / "index.json"
ACCOUNT_USAGE_CACHE = ACCOUNTS_DIR / ".usage-cache.json"

# OAuth 설정
OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
TOKEN_VALIDITY_HOURS = 240        # 토큰 유효기간 (10일)
TOKEN_FRESH_THRESHOLD_HOURS = 230 # 신선도 기준 (잔여 230시간 이상이면 갱신 불필요)

# 갱신 재시도 설정
REFRESH_MAX_RETRIES = 3
REFRESH_RETRY_BACKOFF_BASE = 1

# Soft-block 설정
SOFT_BLOCK_TTL_HOURS = 1
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_config.py -v
```
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add codex_account_manager/config.py tests/test_config.py
git commit -m "feat: config.py — 경로 상수 및 OAuth 설정"
```

---

## Task 3: `auth.py` — auth.json 읽기/쓰기

`~/.codex/auth.json`을 읽고 쓰는 레이어. Claude의 `keychain.py` 역할.

**Files:**
- Create: `codex_account_manager/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_auth.py
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from pathlib import Path
from unittest.mock import patch
from codex_account_manager.auth import read_auth, write_auth, get_access_token, get_refresh_token, get_account_id, is_auth_valid

SAMPLE_AUTH = {
    "auth_mode": "chatgpt",
    "OPENAI_API_KEY": None,
    "tokens": {
        "id_token": "id_tok",
        "access_token": "acc_tok",
        "refresh_token": "rt_tok",
        "account_id": "test-uuid"
    },
    "last_refresh": "2026-05-05T00:00:00Z"
}

def test_read_auth(tmp_path):
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(json.dumps(SAMPLE_AUTH))
    with patch('codex_account_manager.auth.CODEX_AUTH_FILE', auth_file):
        result = read_auth()
    assert result["tokens"]["access_token"] == "acc_tok"

def test_write_auth(tmp_path):
    auth_file = tmp_path / "auth.json"
    with patch('codex_account_manager.auth.CODEX_AUTH_FILE', auth_file):
        write_auth(SAMPLE_AUTH)
    assert json.loads(auth_file.read_text())["tokens"]["refresh_token"] == "rt_tok"
    assert oct(auth_file.stat().st_mode)[-3:] == "600"

def test_get_access_token():
    assert get_access_token(SAMPLE_AUTH) == "acc_tok"

def test_get_refresh_token():
    assert get_refresh_token(SAMPLE_AUTH) == "rt_tok"

def test_get_account_id():
    assert get_account_id(SAMPLE_AUTH) == "test-uuid"

def test_is_auth_valid():
    assert is_auth_valid(SAMPLE_AUTH) is True
    assert is_auth_valid({}) is False
    assert is_auth_valid({"tokens": {}}) is False
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
python3 -m pytest tests/test_auth.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `auth.py` 작성**

```python
"""auth.json 읽기/쓰기 — Claude keychain.py 역할"""
import json
import os
from pathlib import Path
from .config import CODEX_AUTH_FILE


def read_auth(auth_file: Path = None) -> dict | None:
    path = auth_file or CODEX_AUTH_FILE
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def write_auth(data: dict, auth_file: Path = None) -> bool:
    path = auth_file or CODEX_AUTH_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        os.chmod(path, 0o600)
        return True
    except Exception:
        return False


def get_access_token(auth: dict) -> str | None:
    return auth.get("tokens", {}).get("access_token")


def get_refresh_token(auth: dict) -> str | None:
    return auth.get("tokens", {}).get("refresh_token")


def get_account_id(auth: dict) -> str | None:
    return auth.get("tokens", {}).get("account_id")


def is_auth_valid(auth: dict) -> bool:
    if not auth:
        return False
    tokens = auth.get("tokens", {})
    return bool(tokens.get("access_token")) and bool(tokens.get("refresh_token"))
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_auth.py -v
```
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add codex_account_manager/auth.py tests/test_auth.py
git commit -m "feat: auth.py — auth.json 읽기/쓰기"
```

---

## Task 4: `token.py` — OAuth 토큰 갱신

**Files:**
- Create: `codex_account_manager/token.py`
- Create: `tests/test_token.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_token.py
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from codex_account_manager.token import (
    is_token_expired, is_token_expiring_soon, is_token_fresh,
    classify_refresh_error, RefreshError, TokenStatus
)

# access_token은 JWT. 만료 시간 테스트는 last_refresh + TOKEN_VALIDITY_HOURS 기반
FRESH_AUTH = {
    "tokens": {"access_token": "tok", "refresh_token": "rt"},
    "last_refresh": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
}
STALE_AUTH = {
    "tokens": {"access_token": "tok", "refresh_token": "rt"},
    "last_refresh": (datetime.utcnow() - timedelta(hours=235)).strftime("%Y-%m-%dT%H:%M:%SZ")
}
EXPIRED_AUTH = {
    "tokens": {"access_token": "tok", "refresh_token": "rt"},
    "last_refresh": (datetime.utcnow() - timedelta(hours=241)).strftime("%Y-%m-%dT%H:%M:%SZ")
}

def test_is_token_expired_fresh():
    assert is_token_expired(FRESH_AUTH) is False

def test_is_token_expired_old():
    assert is_token_expired(EXPIRED_AUTH) is True

def test_is_token_expiring_soon_stale():
    assert is_token_expiring_soon(STALE_AUTH, hours=10) is True

def test_is_token_fresh():
    assert is_token_fresh(FRESH_AUTH) is True
    assert is_token_fresh(STALE_AUTH) is False

def test_classify_refresh_error_permanent():
    assert classify_refresh_error("invalid_grant") == RefreshError.PERMANENT
    assert classify_refresh_error("HTTP 401 unauthorized") == RefreshError.PERMANENT

def test_classify_refresh_error_transient():
    assert classify_refresh_error("HTTP 500 server error") == RefreshError.TRANSIENT
    assert classify_refresh_error("connection refused") == RefreshError.TRANSIENT
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
python3 -m pytest tests/test_token.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `token.py` 작성**

```python
"""OAuth 토큰 갱신: 만료 확인, 갱신, 상태 분류"""
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta

from .config import (
    TOKEN_VALIDITY_HOURS, TOKEN_FRESH_THRESHOLD_HOURS,
    OAUTH_CLIENT_ID, OAUTH_TOKEN_URL,
    REFRESH_MAX_RETRIES, REFRESH_RETRY_BACKOFF_BASE
)
from .auth import read_auth, write_auth, get_refresh_token, is_auth_valid


class TokenStatus:
    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    NO_TOKEN = "no_token"
    REFRESHED = "refreshed"
    ERROR = "error"


class RefreshError:
    PERMANENT = "permanent"
    TRANSIENT = "transient"


def _last_refresh_dt(auth: dict) -> datetime | None:
    lr = auth.get("last_refresh")
    if not lr:
        return None
    try:
        return datetime.strptime(lr[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def is_token_expired(auth: dict) -> bool:
    dt = _last_refresh_dt(auth)
    if not dt:
        return False
    return datetime.utcnow() > dt + timedelta(hours=TOKEN_VALIDITY_HOURS) - timedelta(minutes=5)


def is_token_expiring_soon(auth: dict, hours: int = 10) -> bool:
    dt = _last_refresh_dt(auth)
    if not dt:
        return False
    expiry = dt + timedelta(hours=TOKEN_VALIDITY_HOURS)
    return datetime.utcnow() > expiry - timedelta(hours=hours)


def is_token_fresh(auth: dict) -> bool:
    dt = _last_refresh_dt(auth)
    if not dt:
        return False
    expiry = dt + timedelta(hours=TOKEN_VALIDITY_HOURS)
    remaining = expiry - datetime.utcnow()
    return remaining >= timedelta(hours=TOKEN_FRESH_THRESHOLD_HOURS)


def classify_refresh_error(error_message: str) -> str:
    if not error_message:
        return RefreshError.TRANSIENT
    msg = error_message.lower()
    if "invalid_grant" in msg or "http 401" in msg:
        return RefreshError.PERMANENT
    return RefreshError.TRANSIENT


def refresh_access_token(auth: dict = None, auth_file=None):
    """refresh_token으로 access_token 갱신.

    Returns: (new_auth, error_message)
    """
    if auth is None:
        auth = read_auth(auth_file)
    if not auth or not is_auth_valid(auth):
        return None, "auth 없음"

    rt = get_refresh_token(auth)
    if not rt:
        return None, "refresh_token 없음"

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": rt,
        "client_id": OAUTH_CLIENT_ID,
    }).encode("utf-8")

    last_error = None
    for attempt in range(REFRESH_MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                OAUTH_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    token_data = json.loads(resp.read().decode())
                    new_auth = json.loads(json.dumps(auth))  # deep copy
                    tokens = new_auth.setdefault("tokens", {})
                    if "access_token" in token_data:
                        tokens["access_token"] = token_data["access_token"]
                    if "refresh_token" in token_data:
                        tokens["refresh_token"] = token_data["refresh_token"]
                    if "id_token" in token_data:
                        tokens["id_token"] = token_data["id_token"]
                    new_auth["last_refresh"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    write_auth(new_auth, auth_file)
                    return new_auth, None

        except urllib.error.HTTPError as e:
            if e.code >= 500 and attempt < REFRESH_MAX_RETRIES:
                wait = REFRESH_RETRY_BACKOFF_BASE * (2 ** attempt)
                time.sleep(wait)
                last_error = f"서버 오류 (HTTP {e.code})"
                continue
            return None, f"토큰 갱신 실패 (HTTP {e.code})"

        except urllib.error.URLError as e:
            if attempt < REFRESH_MAX_RETRIES:
                wait = REFRESH_RETRY_BACKOFF_BASE * (2 ** attempt)
                time.sleep(wait)
                last_error = f"연결 오류: {e.reason}"
                continue
            return None, f"연결 오류: {e.reason}"

        except Exception as e:
            return None, str(e)

    return None, last_error or "알 수 없는 오류"
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_token.py -v
```
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add codex_account_manager/token.py tests/test_token.py
git commit -m "feat: token.py — OAuth 토큰 만료 확인 및 갱신"
```

---

## Task 5: `logger.py` + `ui.py` — 유틸리티

**Files:**
- Create: `codex_account_manager/logger.py`
- Create: `codex_account_manager/ui.py`

- [ ] **Step 1: `logger.py` 작성** (multi-login-claude의 logger.py 포팅)

```python
"""로깅 유틸 — ~/.codex/accounts/logs/token-refresh.log"""
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".codex" / "accounts" / "logs"


def log(level: str, message: str):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / "token-refresh.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass
```

- [ ] **Step 2: `ui.py` 작성** (multi-login-claude의 ui.py 포팅, 동일 색상 코드)

```python
"""컬러 출력 유틸"""

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def colored(text: str, *codes: str) -> str:
    return "".join(codes) + text + Color.RESET


def print_header(title: str):
    print(f"\n{Color.BOLD}{Color.CYAN}{title}{Color.RESET}\n")


def print_success(msg: str):
    print(f"{Color.GREEN}✓{Color.RESET} {msg}")


def print_error(msg: str):
    print(f"{Color.RED}✗{Color.RESET} {msg}")


def print_warn(msg: str):
    print(f"{Color.YELLOW}⚠{Color.RESET} {msg}")
```

- [ ] **Step 3: 커밋**

```bash
git add codex_account_manager/logger.py codex_account_manager/ui.py
git commit -m "feat: logger.py + ui.py 유틸리티"
```

---

## Task 6: `storage.py` — 계정 인덱스 I/O

**Files:**
- Create: `codex_account_manager/storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_storage.py
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pathlib import Path
from unittest.mock import patch
from codex_account_manager.storage import load_index, save_index, find_account, add_account, remove_account

SAMPLE_INDEX = {
    "accounts": [
        {"id": "abc123", "name": "personal", "email": "a@b.com", "account_id": "uuid1", "plan": "Pro"}
    ]
}

def test_load_empty(tmp_path):
    idx_file = tmp_path / "index.json"
    with patch('codex_account_manager.storage.INDEX_FILE', idx_file):
        result = load_index()
    assert result == {"accounts": []}

def test_save_and_load(tmp_path):
    idx_file = tmp_path / "index.json"
    with patch('codex_account_manager.storage.INDEX_FILE', idx_file):
        save_index(SAMPLE_INDEX)
        result = load_index()
    assert result["accounts"][0]["name"] == "personal"

def test_find_account_by_name():
    acct = find_account(SAMPLE_INDEX, "personal")
    assert acct["id"] == "abc123"

def test_find_account_by_id():
    acct = find_account(SAMPLE_INDEX, "abc123")
    assert acct["name"] == "personal"

def test_find_account_not_found():
    assert find_account(SAMPLE_INDEX, "nobody") is None

def test_add_and_remove(tmp_path):
    idx_file = tmp_path / "index.json"
    with patch('codex_account_manager.storage.INDEX_FILE', idx_file):
        save_index({"accounts": []})
        new_acct = {"id": "xyz", "name": "work", "email": "w@c.com", "account_id": "uuid2", "plan": "Pro"}
        add_account(new_acct)
        idx = load_index()
        assert len(idx["accounts"]) == 1
        remove_account("xyz")
        idx = load_index()
        assert len(idx["accounts"]) == 0
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
python3 -m pytest tests/test_storage.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `storage.py` 작성**

```python
"""계정 인덱스(index.json) I/O"""
import json
import os
from pathlib import Path
from .config import ACCOUNTS_DIR, INDEX_FILE


def load_index() -> dict:
    try:
        return json.loads(INDEX_FILE.read_text())
    except Exception:
        return {"accounts": []}


def save_index(index: dict):
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    tmp.rename(INDEX_FILE)


def find_account(index: dict, query: str) -> dict | None:
    for acct in index.get("accounts", []):
        if acct.get("id") == query or acct.get("name") == query:
            return acct
    return None


def add_account(account: dict):
    index = load_index()
    index["accounts"].append(account)
    save_index(index)


def remove_account(account_id: str):
    index = load_index()
    index["accounts"] = [a for a in index["accounts"] if a.get("id") != account_id]
    save_index(index)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_storage.py -v
```
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add codex_account_manager/storage.py tests/test_storage.py
git commit -m "feat: storage.py — 계정 인덱스 I/O"
```

---

## Task 7: `account.py` — 계정 비즈니스 로직

**Files:**
- Create: `codex_account_manager/account.py`

- [ ] **Step 1: `account.py` 작성**

```python
"""계정 비즈니스 로직: 추가, 전환, 삭제"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from .config import ACCOUNTS_DIR, CODEX_AUTH_FILE
from .auth import read_auth, write_auth, get_account_id, is_auth_valid
from .storage import load_index, save_index, find_account, add_account, remove_account
from .token import refresh_access_token, is_token_expiring_soon


def _auth_file_for(account_id: str) -> Path:
    return ACCOUNTS_DIR / f"auth_{account_id}.json"


def get_current_account_info() -> dict | None:
    """현재 로그인된 Codex 계정 정보 반환"""
    auth = read_auth()
    if not auth or not is_auth_valid(auth):
        return None
    return {
        "account_id": get_account_id(auth),
        "auth_mode": auth.get("auth_mode"),
        "last_refresh": auth.get("last_refresh"),
    }


def save_current_account(name: str) -> tuple[bool, str]:
    """현재 로그인 계정을 name으로 저장"""
    auth = read_auth()
    if not auth or not is_auth_valid(auth):
        return False, "현재 로그인된 Codex 계정이 없습니다."

    account_id = get_account_id(auth)
    index = load_index()

    # 이미 등록된 account_id면 스킵
    for acct in index.get("accounts", []):
        if acct.get("account_id") == account_id:
            return False, f"이미 등록된 계정입니다: {acct['name']}"

    short_id = str(uuid.uuid4())[:8]
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    auth_file = _auth_file_for(short_id)
    write_auth(auth, auth_file)

    new_account = {
        "id": short_id,
        "name": name,
        "account_id": account_id,
        "plan": "Unknown",
        "added_at": datetime.now().isoformat(),
        "last_used": datetime.now().isoformat(),
    }
    add_account(new_account)
    return True, short_id


def switch_account(query: str) -> tuple[bool, str]:
    """계정 전환: auth.json 교체"""
    index = load_index()
    acct = find_account(index, query)
    if not acct:
        return False, f"계정을 찾을 수 없습니다: {query}"

    auth_file = _auth_file_for(acct["id"])
    auth = read_auth(auth_file)
    if not auth:
        return False, f"저장된 인증 파일이 없습니다: {auth_file}"

    # 만료 임박 시 갱신
    if is_token_expiring_soon(auth, hours=10):
        new_auth, err = refresh_access_token(auth, auth_file)
        if new_auth:
            auth = new_auth

    write_auth(auth)  # ~/.codex/auth.json 교체

    # last_used 업데이트
    index = load_index()
    for a in index["accounts"]:
        if a["id"] == acct["id"]:
            a["last_used"] = datetime.now().isoformat()
    save_index(index)

    return True, acct["name"]


def delete_account(query: str) -> tuple[bool, str]:
    """저장된 계정 삭제"""
    index = load_index()
    acct = find_account(index, query)
    if not acct:
        return False, f"계정을 찾을 수 없습니다: {query}"

    auth_file = _auth_file_for(acct["id"])
    if auth_file.exists():
        auth_file.unlink()

    remove_account(acct["id"])
    return True, acct["name"]
```

- [ ] **Step 2: 커밋**

```bash
git add codex_account_manager/account.py
git commit -m "feat: account.py — 계정 추가/전환/삭제 비즈니스 로직"
```

---

## Task 8: `api.py` — 사용량 조회

**Files:**
- Create: `codex_account_manager/api.py`

- [ ] **Step 1: `api.py` 작성**

참고: OpenAI 사용량 API 엔드포인트는 현재 공개 문서 미확인. 기본 골격만 구현하고, 사용 불가 시 N/A 반환.

```python
"""OpenAI API — 사용량 조회"""
import urllib.request
import urllib.error
import json

from .auth import read_auth, get_access_token


def fetch_usage(auth: dict = None) -> dict | None:
    """현재 계정 사용량 조회. API 미지원 시 None 반환."""
    if auth is None:
        auth = read_auth()
    if not auth:
        return None

    access_token = get_access_token(auth)
    if not access_token:
        return None

    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/usage",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None
```

- [ ] **Step 2: 커밋**

```bash
git add codex_account_manager/api.py
git commit -m "feat: api.py — OpenAI 사용량 조회 (미지원 시 None)"
```

---

## Task 9: `commands/` — CLI 명령어

**Files:**
- Create: `codex_account_manager/commands/__init__.py`
- Create: `codex_account_manager/commands/list_cmd.py`
- Create: `codex_account_manager/commands/add_cmd.py`
- Create: `codex_account_manager/commands/switch_cmd.py`
- Create: `codex_account_manager/commands/remove_cmd.py`
- Create: `codex_account_manager/commands/token_cmd.py`

- [ ] **Step 1: `commands/__init__.py` — 디스패처**

```python
"""CLI 명령어 디스패처"""
import sys


def dispatch():
    args = sys.argv[1:]
    if not args:
        _print_help()
        return

    cmd = args[0]
    rest = args[1:]

    commands = {
        "list": lambda: _run("list_cmd", rest),
        "add": lambda: _run("add_cmd", rest),
        "switch": lambda: _run("switch_cmd", rest),
        "remove": lambda: _run("remove_cmd", rest),
        "check": lambda: _run("token_cmd", rest),
        "auto-add": lambda: _auto_add(),
    }

    if cmd not in commands:
        print(f"알 수 없는 명령어: {cmd}")
        _print_help()
        sys.exit(1)

    commands[cmd]()


def _run(module_name: str, args: list):
    import importlib
    mod = importlib.import_module(f".{module_name}", package="codex_account_manager.commands")
    mod.run(args)


def _auto_add():
    from codex_account_manager.account import save_current_account, get_current_account_info
    from codex_account_manager.storage import load_index
    from codex_account_manager.auth import get_account_id, read_auth

    auth = read_auth()
    if not auth:
        return

    account_id = get_account_id(auth)
    index = load_index()
    for acct in index.get("accounts", []):
        if acct.get("account_id") == account_id:
            return  # 이미 등록됨

    ok, result = save_current_account(account_id[:8] if account_id else "default")
    if ok:
        print(f"[account] 계정 자동 등록: {result}", flush=True)


def _print_help():
    print("""codex account manager
사용법: python3 account_manager.py <command> [args]

명령어:
  list              계정 목록 표시
  add [name]        현재 계정 저장
  switch <id|name>  계정 전환
  remove <id|name>  계정 삭제
  check             현재 토큰 상태 확인
""")
```

- [ ] **Step 2: `commands/list_cmd.py` 작성**

```python
"""list: 저장된 계정 목록 표시"""
from codex_account_manager.storage import load_index
from codex_account_manager.auth import read_auth, get_account_id
from codex_account_manager.ui import Color, print_header


def run(args: list):
    print_header("Codex 계정 목록")
    index = load_index()
    accounts = index.get("accounts", [])

    if not accounts:
        print("  저장된 계정이 없습니다. `add` 명령어로 계정을 추가하세요.")
        return

    current_auth = read_auth()
    current_id = get_account_id(current_auth) if current_auth else None

    for acct in accounts:
        is_current = acct.get("account_id") == current_id
        marker = f"{Color.GREEN}●{Color.RESET}" if is_current else " "
        name = f"{Color.BOLD}{acct['name']}{Color.RESET}"
        plan = acct.get("plan", "Unknown")
        acct_id = acct.get("id", "")
        print(f"  {marker} [{acct_id}] {name}  ({plan})")
```

- [ ] **Step 3: `commands/add_cmd.py` 작성**

```python
"""add: 현재 로그인 계정 저장"""
from codex_account_manager.account import save_current_account
from codex_account_manager.ui import print_success, print_error


def run(args: list):
    name = args[0] if args else None
    if not name:
        print("사용법: add <name>")
        return

    ok, result = save_current_account(name)
    if ok:
        print_success(f"계정 저장됨: {name} (id: {result})")
    else:
        print_error(result)
```

- [ ] **Step 4: `commands/switch_cmd.py` 작성**

```python
"""switch: 계정 전환"""
from codex_account_manager.account import switch_account
from codex_account_manager.ui import print_success, print_error


def run(args: list):
    if not args:
        print("사용법: switch <id|name>")
        return

    query = args[0]
    ok, result = switch_account(query)
    if ok:
        print_success(f"계정 전환됨: {result}")
        print("  새 세션에서 적용됩니다.")
    else:
        print_error(result)
```

- [ ] **Step 5: `commands/remove_cmd.py` 작성**

```python
"""remove: 저장된 계정 삭제"""
from codex_account_manager.account import delete_account
from codex_account_manager.ui import print_success, print_error


def run(args: list):
    if not args:
        print("사용법: remove <id|name>")
        return

    query = args[0]
    ok, result = delete_account(query)
    if ok:
        print_success(f"계정 삭제됨: {result}")
    else:
        print_error(result)
```

- [ ] **Step 6: `commands/token_cmd.py` 작성**

```python
"""check: 현재 토큰 상태 확인"""
from codex_account_manager.auth import read_auth, is_auth_valid
from codex_account_manager.token import is_token_expired, is_token_expiring_soon, is_token_fresh
from codex_account_manager.ui import print_success, print_error, print_warn


def run(args: list):
    auth = read_auth()
    if not auth or not is_auth_valid(auth):
        print_error("로그인된 Codex 계정이 없습니다.")
        return

    last_refresh = auth.get("last_refresh", "알 수 없음")
    print(f"  마지막 갱신: {last_refresh}")

    if is_token_expired(auth):
        print_error("토큰 만료됨 — 재로그인 필요 (codex login)")
    elif is_token_expiring_soon(auth, hours=24):
        print_warn("토큰 곧 만료 (24시간 내)")
    elif is_token_fresh(auth):
        print_success("토큰 정상 (충분한 잔여 시간)")
    else:
        print_warn("토큰 갱신 권장")
```

- [ ] **Step 7: 기본 동작 확인**

```bash
python3 account_manager.py --help 2>/dev/null || python3 account_manager.py
python3 account_manager.py list
python3 account_manager.py check
```
Expected: 오류 없이 출력됨

- [ ] **Step 8: 커밋**

```bash
git add codex_account_manager/commands/
git commit -m "feat: CLI 명령어 구현 (list/add/switch/remove/check)"
```

---

## Task 10: 훅 스크립트

**Files:**
- Create: `hooks-handlers/session-start.sh`
- Create: `hooks-handlers/prompt-submit.sh`

- [ ] **Step 1: `hooks-handlers/session-start.sh` 작성**

```bash
#!/usr/bin/env bash
# 세션 시작 시: 현재 계정 자동 등록 + 만료 토큰 일괄 갱신

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
LOG_DIR="$HOME/.codex/accounts/logs"
mkdir -p "$LOG_DIR"

# 현재 계정 자동 등록
python3 "$SCRIPT_DIR/account_manager.py" auto-add 2>>"$LOG_DIR/token-refresh.log"

# 저장된 모든 계정 토큰 갱신 (만료 임박 시)
python3 "$SCRIPT_DIR/account_manager.py" refresh-all 2>>"$LOG_DIR/token-refresh.log"

exit 0
```

- [ ] **Step 2: `hooks-handlers/prompt-submit.sh` 작성**

```bash
#!/usr/bin/env bash
# 메시지 입력 시: 현재 계정 토큰이 24시간 내 만료 예정이면 갱신

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
LOG_DIR="$HOME/.codex/accounts/logs"

python3 "$SCRIPT_DIR/account_manager.py" refresh-current 2>>"$LOG_DIR/token-refresh.log"

exit 0
```

- [ ] **Step 3: 실행 권한 부여**

```bash
chmod +x hooks-handlers/session-start.sh hooks-handlers/prompt-submit.sh
```

- [ ] **Step 4: `commands/__init__.py`에 refresh-all, refresh-current 추가**

`dispatch()` 함수의 `commands` dict에 추가:
```python
"refresh-all": lambda: _refresh_all(),
"refresh-current": lambda: _refresh_current(),
```

`_refresh_all` 함수 추가:
```python
def _refresh_all():
    from codex_account_manager.storage import load_index
    from codex_account_manager.auth import read_auth
    from codex_account_manager.token import refresh_access_token, is_token_expiring_soon
    from codex_account_manager.config import ACCOUNTS_DIR
    from pathlib import Path

    index = load_index()
    for acct in index.get("accounts", []):
        auth_file = ACCOUNTS_DIR / f"auth_{acct['id']}.json"
        auth = read_auth(auth_file)
        if auth and is_token_expiring_soon(auth, hours=24):
            new_auth, err = refresh_access_token(auth, auth_file)
            label = acct.get("name", acct["id"])
            if new_auth:
                print(f"[refresh] {label}: 갱신됨", flush=True)
            else:
                print(f"[refresh] {label}: 갱신 실패 - {err}", flush=True)
        else:
            label = acct.get("name", acct["id"])
            print(f"[refresh] {label}: 최근 갱신됨 → 스킵", flush=True)
```

`_refresh_current` 함수 추가:
```python
def _refresh_current():
    from codex_account_manager.auth import read_auth, is_auth_valid
    from codex_account_manager.token import refresh_access_token, is_token_expiring_soon

    auth = read_auth()
    if not auth or not is_auth_valid(auth):
        return
    if is_token_expiring_soon(auth, hours=1):
        new_auth, err = refresh_access_token(auth)
        if new_auth:
            print("[refresh] 현재 계정 토큰 갱신됨", flush=True)
```

- [ ] **Step 5: 커밋**

```bash
git add hooks-handlers/ codex_account_manager/commands/__init__.py
git commit -m "feat: 훅 스크립트 및 refresh-all/refresh-current 명령어"
```

---

## Task 11: `skills/` — oh-my-codex SKILL.md

**Files:**
- Create: `skills/list/SKILL.md`
- Create: `skills/add/SKILL.md`
- Create: `skills/switch/SKILL.md`
- Create: `skills/remove/SKILL.md`
- Create: `skills/check/SKILL.md`

- [ ] **Step 1: `skills/list/SKILL.md` 작성**

```markdown
# account:list

저장된 Codex 계정 목록과 현재 활성 계정을 표시한다.

## 실행

다음 명령어를 Bash로 실행한다:

```bash
python3 "$(ls -1d ~/.codex/skills/account/*/account_manager.py 2>/dev/null | head -1 || echo 'account_manager.py')" list
```

결과를 그대로 사용자에게 보여준다.
```

- [ ] **Step 2: `skills/add/SKILL.md` 작성**

```markdown
# account:add

현재 로그인된 Codex 계정을 지정한 이름으로 저장한다.

## 실행

args에서 name을 추출하고 다음을 실행:

```bash
python3 "$HOME/.codex/skills/account/current/account_manager.py" add <name>
```
```

- [ ] **Step 3: `skills/switch/SKILL.md` 작성**

```markdown
# account:switch

저장된 계정으로 전환한다. 전환 후 Codex를 재시작해야 적용된다.

## 실행

```bash
python3 "$HOME/.codex/skills/account/current/account_manager.py" switch <id|name>
```
```

- [ ] **Step 4: `skills/remove/SKILL.md` 작성**

```markdown
# account:remove

저장된 계정을 삭제한다. 현재 활성 계정은 삭제되지 않는다.

## 실행

```bash
python3 "$HOME/.codex/skills/account/current/account_manager.py" remove <id|name>
```
```

- [ ] **Step 5: `skills/check/SKILL.md` 작성**

```markdown
# account:check

현재 Codex OAuth 토큰 상태를 확인한다.

## 실행

```bash
python3 "$HOME/.codex/skills/account/current/account_manager.py" check
```
```

- [ ] **Step 6: 커밋**

```bash
git add skills/
git commit -m "feat: oh-my-codex 스킬 SKILL.md 추가"
```

---

## Task 12: `install.sh` — 훅 주입 및 alias 설치

**Files:**
- Create: `install.sh`

- [ ] **Step 1: `install.sh` 작성**

```bash
#!/usr/bin/env bash
set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
CODEX_DIR="$HOME/.codex"
HOOKS_FILE="$CODEX_DIR/hooks.json"
SKILLS_DIR="$CODEX_DIR/skills"

echo "multi-login-codex 설치 중..."

# 1. ~/.codex/skills/account/ 링크 생성
mkdir -p "$SKILLS_DIR/account"
ln -sf "$PLUGIN_DIR" "$SKILLS_DIR/account/current"
echo "✓ 스킬 링크 생성: $SKILLS_DIR/account/current"

# 2. hooks.json에 훅 주입
if [ ! -f "$HOOKS_FILE" ]; then
    echo '{"hooks":{}}' > "$HOOKS_FILE"
fi

python3 - <<PYEOF
import json, sys
from pathlib import Path

hooks_file = Path("$HOOKS_FILE")
plugin_dir = "$PLUGIN_DIR"
data = json.loads(hooks_file.read_text())
hooks = data.setdefault("hooks", {})

session_hook = {
    "matcher": "startup|resume",
    "hooks": [{"type": "command", "command": f"{plugin_dir}/hooks-handlers/session-start.sh"}]
}
prompt_hook = {
    "hooks": [{"type": "command", "command": f"{plugin_dir}/hooks-handlers/prompt-submit.sh"}]
}

# 중복 방지: 이미 있으면 스킵
ss_hooks = hooks.setdefault("SessionStart", [])
if not any(h.get("hooks", [{}])[0].get("command", "").endswith("session-start.sh") for h in ss_hooks):
    ss_hooks.append(session_hook)

up_hooks = hooks.setdefault("UserPromptSubmit", [])
if not any(h.get("hooks", [{}])[0].get("command", "").endswith("prompt-submit.sh") for h in up_hooks if h.get("hooks")):
    up_hooks.append(prompt_hook)

hooks_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
print("✓ hooks.json 훅 주입 완료")
PYEOF

# 3. shell alias 설정
SHELL_RC=""
if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "/bin/zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [ "$SHELL" = "/bin/bash" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

MARKER_BEGIN="# >>> codex-account-manager >>>"
MARKER_END="# <<< codex-account-manager <<<"

if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    if grep -q "$MARKER_BEGIN" "$SHELL_RC" 2>/dev/null; then
        echo "✓ shell alias 이미 설치됨"
    else
        cat >> "$SHELL_RC" <<ALIAS

$MARKER_BEGIN
_codex_account_run() {
    python3 "$PLUGIN_DIR/account_manager.py" "\$@"
}
alias account='_codex_account_run'
$MARKER_END
ALIAS
        echo "✓ shell alias 추가됨 ($SHELL_RC)"
    fi
fi

echo ""
echo "설치 완료! 적용하려면:"
echo "  source $SHELL_RC"
echo ""
echo "사용법:"
echo "  account list"
echo "  account add <name>"
echo "  account switch <name>"
```

- [ ] **Step 2: 실행 권한 부여**

```bash
chmod +x install.sh
```

- [ ] **Step 3: 설치 테스트 (dry-run)**

```bash
bash -n install.sh && echo "문법 OK"
```
Expected: `문법 OK`

- [ ] **Step 4: 커밋**

```bash
git add install.sh
git commit -m "feat: install.sh — hooks.json 주입 및 alias 설치"
```

---

## Task 13: 전체 테스트 실행 및 최종 확인

- [ ] **Step 1: 전체 테스트 실행**

```bash
cd /Users/ezhoon/Desktop/ai-project/multi-login-codex
python3 -m pytest tests/ -v
```
Expected: 모두 PASS

- [ ] **Step 2: 기본 동작 확인**

```bash
python3 account_manager.py list
python3 account_manager.py check
```
Expected: 오류 없이 동작

- [ ] **Step 3: GitHub 레포 생성 및 push**

```bash
gh repo create lee-ji-hoon/multi-login-codex --public --source=. --remote=origin
git push -u origin main
```

- [ ] **Step 4: 최종 커밋**

```bash
git add .
git commit -m "release: v1.0.0 initial release" --allow-empty
```
