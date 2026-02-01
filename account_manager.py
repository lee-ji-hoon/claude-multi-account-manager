#!/usr/bin/env python3
"""
Claude Code Multi-Account Manager
다중 계정을 관리하는 스크립트

Usage:
    python3 account_manager.py [action] [args]

Actions:
    list           - 등록된 계정 목록 (사용량 시각화 포함)
    add [name]     - 현재 계정 저장
    switch [id]    - 계정 전환 (인자 없으면 대화형 선택)
    remove [id]    - 계정 삭제
    rename [id] [name] - 계정 이름 변경
    current        - 현재 계정 표시

This file is a thin wrapper for backward compatibility.
The actual implementation is in the claude_account_manager package.
"""

from claude_account_manager import main, __version__

if __name__ == "__main__":
    main()
