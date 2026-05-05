"""Codex 계정 통합 브리지 — ~/.codex/auth.json 읽기/쓰기"""
from pathlib import Path
import json, os


def _decode_jwt_payload(token: str) -> dict:
    """JWT 페이로드(중간 segment) base64 디코딩. 실패 시 {}."""
    try:
        import base64
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        pad = parts[1] + "=="
        return json.loads(base64.urlsafe_b64decode(pad))
    except Exception:
        return {}


def get_codex_auth_info(auth: dict) -> dict:
    """access_token/id_token JWT에서 name, email, plan 추출."""
    tokens = auth.get("tokens", {}) if auth else {}
    info = {}
    at = _decode_jwt_payload(tokens.get("access_token", ""))
    it = _decode_jwt_payload(tokens.get("id_token", ""))

    info["email"] = (
        at.get("https://api.openai.com/profile", {}).get("email")
        or it.get("email")
        or ""
    )
    info["name"] = it.get("name") or info["email"].split("@")[0] if info["email"] else ""
    raw_plan = at.get("https://api.openai.com/auth", {}).get("chatgpt_plan_type", "")
    info["plan"] = raw_plan.capitalize() if raw_plan else "Free"
    return info

CODEX_DIR = Path.home() / ".codex"
CODEX_AUTH_FILE = CODEX_DIR / "auth.json"
CODEX_ACCOUNTS_DIR = CODEX_DIR / "accounts"
CODEX_INDEX_FILE = CODEX_ACCOUNTS_DIR / "index.json"


def is_codex_available() -> bool:
    """multi-login-codex 계정 인덱스가 존재하는지 확인"""
    return CODEX_INDEX_FILE.exists()


def load_codex_index() -> dict:
    try:
        return json.loads(CODEX_INDEX_FILE.read_text())
    except Exception:
        return {"accounts": []}


def read_codex_auth(auth_file: Path = None) -> dict | None:
    path = auth_file or CODEX_AUTH_FILE
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def write_codex_auth(data: dict, auth_file: Path = None) -> bool:
    path = auth_file or CODEX_AUTH_FILE
    try:
        import tempfile
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=path.parent)
        try:
            os.write(fd, json.dumps(data, indent=2, ensure_ascii=False).encode())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, path)
        finally:
            os.close(fd)
        return True
    except Exception:
        return False


def get_current_codex_account_id() -> str | None:
    """현재 활성 Codex 계정의 account_id 반환"""
    auth = read_codex_auth()
    if not auth:
        return None
    return auth.get("tokens", {}).get("account_id")


def get_codex_token_status(acc: dict) -> str:
    """
    계정의 토큰 상태 반환: 'ok' | 'expiring' | 'expired' | 'no_auth'
    last_refresh 기준 (240시간 유효기간)
    """
    from datetime import datetime, timedelta
    auth_file = CODEX_ACCOUNTS_DIR / f"auth_{acc['id']}.json"
    auth = read_codex_auth(auth_file)
    if not auth:
        return "no_auth"
    lr = auth.get("last_refresh")
    if not lr:
        return "expired"
    try:
        dt = datetime.strptime(lr[:19], "%Y-%m-%dT%H:%M:%S")
        expiry = dt + timedelta(hours=240)
        now = datetime.utcnow()
        if now > expiry - timedelta(minutes=5):
            return "expired"
        if now > expiry - timedelta(hours=24):
            return "expiring"
        return "ok"
    except Exception:
        return "expired"


def switch_codex_account(acc: dict) -> tuple[bool, str]:
    """Codex 계정으로 전환: auth_file → ~/.codex/auth.json 교체"""
    from datetime import datetime
    auth_file = CODEX_ACCOUNTS_DIR / f"auth_{acc['id']}.json"
    auth = read_codex_auth(auth_file)
    if not auth:
        return False, f"인증 파일 없음: auth_{acc['id']}.json"

    # 백업
    backup_dir = CODEX_ACCOUNTS_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    current = read_codex_auth()
    if current:
        bk = backup_dir / f"auth_{ts}.json"
        try:
            import tempfile
            fd, tmp = tempfile.mkstemp(dir=backup_dir)
            os.write(fd, json.dumps(current, indent=2, ensure_ascii=False).encode())
            os.chmod(tmp, 0o600)
            os.replace(tmp, bk)
        except Exception:
            pass
        finally:
            try:
                os.close(fd)
            except Exception:
                pass
        # 오래된 백업 정리 (최근 5개)
        backups = sorted(backup_dir.glob("auth_*.json"), key=lambda p: p.stat().st_mtime)
        for old in backups[:-5]:
            try:
                old.unlink()
            except Exception:
                pass

    if write_codex_auth(auth):
        # last_used 업데이트
        try:
            index = load_codex_index()
            for a in index["accounts"]:
                if a["id"] == acc["id"]:
                    a["last_used"] = datetime.now().isoformat()
            CODEX_ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
            tmp2 = CODEX_INDEX_FILE.with_suffix(".tmp")
            tmp2.write_text(json.dumps(index, indent=2, ensure_ascii=False))
            tmp2.rename(CODEX_INDEX_FILE)
        except Exception:
            pass
        return True, acc["name"]
    return False, "auth.json 쓰기 실패"


def fetch_codex_usage(auth: dict) -> dict | None:
    """
    /backend-api/codex/usage 호출. ChatGPT-Account-Id 헤더 필요.
    반환: rate_limit 딕셔너리 또는 None
    """
    import urllib.request, urllib.error
    tokens = auth.get("tokens", {}) if auth else {}
    access_token = tokens.get("access_token", "")
    if not access_token:
        return None
    at = _decode_jwt_payload(access_token)
    account_id = at.get("https://api.openai.com/auth", {}).get("chatgpt_account_id", "")
    try:
        req = urllib.request.Request(
            "https://chatgpt.com/backend-api/codex/usage",
            headers={
                "Authorization": f"Bearer {access_token}",
                "ChatGPT-Account-Id": account_id,
                "User-Agent": "codex-cli/0.128.0",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def add_codex_account(name: str = None) -> tuple[bool, str]:
    """현재 ~/.codex/auth.json을 Codex 계정으로 저장"""
    import hashlib
    from datetime import datetime

    auth = read_codex_auth()
    if not auth:
        return False, "~/.codex/auth.json 없음 — codex login 먼저 실행하세요"

    tokens = auth.get("tokens", {})
    account_id = tokens.get("account_id")
    if not account_id:
        return False, "auth.json에 account_id가 없습니다"

    # 8자리 단축 ID (account_id 해시)
    short_id = hashlib.md5(account_id.encode()).hexdigest()[:8]

    # 중복 확인
    if is_codex_available():
        index = load_codex_index()
        for acc in index.get("accounts", []):
            if acc.get("account_id") == account_id:
                return False, f"이미 등록된 계정입니다: {acc['name']} (id: {acc['id']})"
    else:
        index = {"accounts": []}

    # JWT에서 실제 name, email, plan 추출
    info = get_codex_auth_info(auth)
    if not name:
        name = info.get("name") or info.get("email", "").split("@")[0] or f"codex-{short_id[:4]}"
    email = info.get("email", "")
    plan = info.get("plan", "Free")

    # auth 파일 저장
    CODEX_ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    auth_file = CODEX_ACCOUNTS_DIR / f"auth_{short_id}.json"
    if not write_codex_auth(auth, auth_file):
        return False, "auth 파일 저장 실패"

    # index 업데이트
    now = datetime.now().isoformat()
    index["accounts"].append({
        "id": short_id,
        "name": name,
        "email": email,
        "account_id": account_id,
        "plan": plan,
        "added_at": now,
        "last_used": now,
    })
    try:
        tmp = CODEX_INDEX_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False))
        tmp.rename(CODEX_INDEX_FILE)
    except Exception as e:
        return False, f"index 저장 실패: {e}"

    return True, f"{name} (id: {short_id})"


def remove_codex_account(acc: dict) -> tuple[bool, str]:
    """저장된 Codex 계정 삭제"""
    # auth 파일 삭제
    auth_file = CODEX_ACCOUNTS_DIR / f"auth_{acc['id']}.json"
    if auth_file.exists():
        auth_file.unlink()
    # index에서 제거
    try:
        index = load_codex_index()
        index["accounts"] = [a for a in index["accounts"] if a["id"] != acc["id"]]
        tmp = CODEX_INDEX_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False))
        tmp.rename(CODEX_INDEX_FILE)
    except Exception as e:
        return False, str(e)
    return True, acc["name"]
