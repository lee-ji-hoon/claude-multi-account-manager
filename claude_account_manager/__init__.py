"""
Claude Account Manager - Multi-account management for Claude Code

This package provides tools to manage multiple Claude accounts,
including OAuth token management and account switching.
"""

from .config import __version__, PACKAGE_NAME
from .commands import main

# Re-export commonly used functions for backward compatibility
from .keychain import get_keychain_credential, set_keychain_credential
from .storage import load_index, save_index, load_claude_json, save_claude_json, get_current_account
from .token import TokenStatus, refresh_access_token, check_token_status
from .api import get_real_usage, _fetch_usage_from_api, get_today_usage, get_weekly_usage
from .account import estimate_plan, detect_plan_from_credential

__all__ = [
    # Version info
    "__version__",
    "PACKAGE_NAME",
    # Main entry point
    "main",
    # Keychain
    "get_keychain_credential",
    "set_keychain_credential",
    # Storage
    "load_index",
    "save_index",
    "load_claude_json",
    "save_claude_json",
    "get_current_account",
    # Token
    "TokenStatus",
    "refresh_access_token",
    "check_token_status",
    # API
    "get_real_usage",
    "_fetch_usage_from_api",
    "get_today_usage",
    "get_weekly_usage",
    # Account
    "estimate_plan",
    "detect_plan_from_credential",
]
