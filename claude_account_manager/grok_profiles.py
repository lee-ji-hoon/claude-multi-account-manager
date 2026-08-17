"""Grok account profiles backed by isolated, official ``GROK_HOME`` roots.

Switchboard never copies or swaps ``auth.json``.  A profile is an independent
Grok home and is only activated by launching a *new* Grok process with the
returned environment.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Dict, List


_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _default_grok_home() -> Path:
    return Path.home() / ".grok"


def _profiles_root() -> Path:
    configured = os.environ.get("SWITCHBOARD_GROK_PROFILES_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".grok-profiles"


def _profile_home(account_id: str) -> Path:
    if account_id == "default":
        return _default_grok_home()
    if not _PROFILE_ID.fullmatch(account_id) or account_id in (".", ".."):
        raise ValueError("유효하지 않은 Grok 프로필 ID입니다")
    root = _profiles_root()
    candidate = root / account_id
    # Profiles must be real direct children.  Refusing symlinks keeps a
    # registry entry from silently retargeting to another credential store.
    if candidate.is_symlink():
        raise ValueError("심볼릭 링크 Grok 프로필은 지원하지 않습니다")
    return candidate


def _is_authenticated_home(path: Path) -> bool:
    auth_file = path / "auth.json"
    return path.is_dir() and auth_file.is_file() and not auth_file.is_symlink()


def list_grok_profiles() -> List[Dict[str, object]]:
    """Return allowlisted profile metadata without reading credential content."""
    profiles = []
    default_home = _default_grok_home()
    if _is_authenticated_home(default_home):
        profiles.append(
            {
                "accountID": "default",
                "grokHome": str(default_home),
                "authenticated": True,
            }
        )

    root = _profiles_root()
    try:
        children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        children = []
    for child in children:
        if (
            _PROFILE_ID.fullmatch(child.name)
            and child.name not in (".", "..")
            and not child.is_symlink()
            and _is_authenticated_home(child)
        ):
            profiles.append(
                {
                    "accountID": child.name,
                    "grokHome": str(child),
                    "authenticated": True,
                }
            )
    return profiles


def get_grok_launch_contract(account_id: str) -> Dict[str, object]:
    """Build the environment for a new Grok process.

    This function does not launch a process and does not mutate the current
    Grok session or any ``auth.json`` file.
    """
    profile_home = _profile_home(account_id)
    if not _is_authenticated_home(profile_home):
        raise ValueError("로그인된 Grok 프로필을 찾을 수 없습니다: %s" % account_id)
    return {
        "accountID": account_id,
        "executable": "grok",
        "arguments": [],
        "environment": {"GROK_HOME": str(profile_home)},
    }
