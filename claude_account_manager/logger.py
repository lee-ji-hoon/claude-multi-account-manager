"""
Lightweight file logger for token refresh diagnostics.
Standard library only. Never raises exceptions.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path

from .config import ACCOUNTS_DIR

LOG_DIR = ACCOUNTS_DIR / "logs"
LOG_FILE = LOG_DIR / "token-refresh.log"
LOG_BACKUP = LOG_DIR / "token-refresh.log.1"
MAX_LOG_SIZE = 512 * 1024  # 512KB


def _ensure_log_dir():
    """로그 디렉토리 생성"""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if not LOG_FILE.exists():
            LOG_FILE.touch(mode=0o600)
        elif (LOG_FILE.stat().st_mode & 0o777) != 0o600:
            os.chmod(LOG_FILE, 0o600)
    except Exception:
        pass


def _rotate_if_needed():
    """로그 파일 크기 초과 시 회전"""
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_SIZE:
            if LOG_BACKUP.exists():
                LOG_BACKUP.unlink()
            LOG_FILE.rename(LOG_BACKUP)
    except Exception:
        pass


def log(level, message):
    """로그 기록

    Args:
        level: "INFO", "WARN", "ERROR"
        message: 로그 메시지
    """
    try:
        _ensure_log_dir()
        _rotate_if_needed()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {level:<5} {message}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def log_token_info(account_id, credential, prefix=""):
    """토큰 만료 정보 로깅

    Args:
        account_id: 계정 ID
        credential: credential 딕셔너리
        prefix: 로그 메시지 접두사
    """
    try:
        oauth = credential.get("claudeAiOauth", {})
        expires_at = oauth.get("expiresAt")
        if expires_at:
            expires_dt = datetime.fromtimestamp(expires_at / 1000)
            remaining = expires_dt - datetime.now()
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            expires_str = expires_dt.strftime("%Y-%m-%d %H:%M:%S")

            if remaining.total_seconds() < 0:
                log("WARN", f"[{account_id}] {prefix}만료됨 (만료: {expires_str}, {abs(hours)}h{abs(minutes)}m 전)")
            else:
                log("INFO", f"[{account_id}] {prefix}토큰 상태 (만료: {expires_str}, 잔여: {hours}h{minutes}m)")
        else:
            log("WARN", f"[{account_id}] {prefix}expiresAt 없음")
    except Exception:
        pass


def get_log_path():
    """로그 파일 경로 반환"""
    return LOG_FILE


def read_log_lines(n=50):
    """최근 로그 N줄 읽기

    Args:
        n: 읽을 줄 수 (기본 50)

    Returns:
        list[str]: 로그 라인 리스트 (파일 없으면 빈 리스트)
    """
    try:
        if not LOG_FILE.exists():
            return []
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-n:]
    except Exception:
        return []
