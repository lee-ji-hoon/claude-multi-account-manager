"""Codex 계정 통합 브리지 — ~/.codex/auth.json 읽기/쓰기"""
from pathlib import Path
import json, os

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
