"""
File I/O operations for account data persistence
"""
import json

from .config import ACCOUNTS_DIR, INDEX_FILE, CLAUDE_JSON


def ensure_accounts_dir():
    """accounts 디렉토리와 index.json 초기화"""
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text(json.dumps({
            "version": 1,
            "accounts": [],
            "activeAccountId": None
        }, indent=2, ensure_ascii=False))


def load_index():
    """index.json 로드"""
    ensure_accounts_dir()
    try:
        return json.loads(INDEX_FILE.read_text())
    except json.JSONDecodeError:
        # 손상된 index.json 복구
        default_index = {
            "version": 1,
            "accounts": [],
            "activeAccountId": None
        }
        save_index(default_index)
        return default_index


def save_index(data):
    """index.json 저장"""
    INDEX_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_claude_json():
    """~/.claude.json 로드"""
    if not CLAUDE_JSON.exists():
        return {}
    try:
        return json.loads(CLAUDE_JSON.read_text())
    except json.JSONDecodeError as e:
        print(f"~/.claude.json 파싱 오류: {e}")
        return {}


def save_claude_json(data):
    """~/.claude.json 저장"""
    CLAUDE_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def get_current_account():
    """현재 oauthAccount 반환"""
    data = load_claude_json()
    return data.get("oauthAccount", {})
