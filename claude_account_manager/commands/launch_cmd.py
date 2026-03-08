"""
cmd_launch: Interactive Claude Code launcher.

Shows:
1. Current account + usage
2. Running Claude sessions
3. Registered accounts
Then lets user pick action: continue, resume, switch account, or new session.
"""
import json
import os
import subprocess
import sys
from datetime import datetime

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors, make_progress_bar
from ..storage import load_index, get_current_account
from ..account import estimate_plan, is_same_account, _is_real_org
from ..api import get_real_usage
from ..token import TokenStatus


def cmd_launch(extra_args=None):
    """대화형 Claude Code 런처"""
    index = load_index()
    current = get_current_account()
    current_email = current.get("emailAddress", "")

    print()
    print(c(Colors.BOLD, "  Claude Code Launcher"))
    print(c(Colors.DIM, "  " + "=" * 50))

    # 1. 현재 계정 표시
    if current_email:
        plan = estimate_plan(current)
        org_name = current.get("organizationName", "")
        org_badge = f" @{org_name}" if _is_real_org(org_name) else ""
        print(f"  현재: {c(Colors.GREEN, current_email)}{org_badge} [{plan}]")

        # 사용량 (빠른 조회)
        try:
            usage = get_real_usage()
            if usage and usage.get("fiveHour") is not None:
                pct = usage["fiveHour"]
                bar = make_progress_bar(pct, width=10)
                print(f"  사용량: {bar} {pct}%")
        except Exception:
            pass
    else:
        print(f"  현재: {c(Colors.YELLOW, '로그인 안 됨')}")

    # 2. 실행 중인 Claude 세션
    sessions = _find_running_sessions()
    if sessions:
        print()
        print(c(Colors.CYAN, "  실행 중인 세션:"))
        for sess in sessions:
            print(f"    {c(Colors.DIM, '•')} {sess}")

    # 3. 등록된 계정 목록 (간략)
    if index["accounts"]:
        print()
        print(c(Colors.DIM, "  " + "-" * 50))
        print(c(Colors.BOLD, "  등록된 계정:"))
        for i, acc in enumerate(index["accounts"], 1):
            is_current = is_same_account(acc, current) if current_email else False
            marker = c(Colors.GREEN, "●") if is_current else " "
            plan = acc.get("plan", "?")
            acc_org = acc.get("organizationName", "")
            org_badge = f" @{acc_org}" if _is_real_org(acc_org) else ""
            print(f"  [{i}] {marker} {acc['name']}{org_badge} [{plan}] {c(Colors.DIM, acc['email'])}")

    # 4. 선택지
    print()
    print(c(Colors.DIM, "  " + "-" * 50))
    print(f"  {c(Colors.CYAN, '[Enter]')} 새 세션 시작")
    print(f"  {c(Colors.CYAN, '[c]')}     이전 대화 이어가기")
    print(f"  {c(Colors.CYAN, '[r]')}     대화 선택 (resume)")
    if len(index["accounts"]) > 1:
        print(f"  {c(Colors.CYAN, '[s]')}     계정 전환 후 시작")
    print(f"  {c(Colors.CYAN, '[q]')}     취소")
    print(c(Colors.DIM, "  " + "-" * 50))
    print(f"  선택: ", end="", flush=True)

    try:
        choice = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    args = extra_args or []

    if choice == 'q':
        return
    elif choice == 'c':
        _exec_claude(["--continue"] + args)
    elif choice == 'r':
        _exec_claude(["--resume"] + args)
    elif choice == 's' and len(index["accounts"]) > 1:
        # 계정 전환
        from .switch_cmd import cmd_switch
        if cmd_switch():
            print(c(Colors.YELLOW, "  Claude Code를 시작합니다..."))
            _exec_claude(args)
    elif choice == '':
        _exec_claude(args)
    else:
        # 숫자면 계정 선택 후 시작
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(index["accounts"]):
                from .switch_cmd import cmd_switch
                acc_id = index["accounts"][idx]["id"]
                if cmd_switch(acc_id):
                    _exec_claude(args)
            else:
                print(f"  잘못된 번호: {choice}")
        except ValueError:
            print(f"  알 수 없는 선택: {choice}")


def _find_running_sessions():
    """실행 중인 Claude Code 세션 찾기"""
    sessions = []

    # Claude Code 메인 프로세스 찾기 (plugin/node 프로세스 제외)
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split('\n'):
            # Claude Code CLI 프로세스만 (node 기반의 @anthropic-ai/claude-code)
            if 'claude-code' in line and 'node' in line:
                # plugin, snapshot, shell 프로세스 제외
                if any(skip in line for skip in ['plugins/', 'shell-snapshots/', 'account_manager']):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    pid = parts[1]
                    # 작업 디렉토리 찾기
                    try:
                        cwd_result = subprocess.run(
                            ["lsof", "-p", pid, "-Fn"],
                            capture_output=True, text=True, timeout=3
                        )
                        cwd = ""
                        for cwd_line in cwd_result.stdout.split('\n'):
                            if cwd_line.startswith('n') and cwd_line.startswith('n/'):
                                cwd = cwd_line[1:]
                                break
                    except Exception:
                        cwd = ""
                    path_display = cwd.replace(os.path.expanduser("~"), "~") if cwd else ""
                    sessions.append(f"PID {pid} {path_display}")
    except Exception:
        pass

    # tmux 세션 (Claude가 실행 중일 수 있는 것만)
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_windows}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split(':')
                name = parts[0]
                windows = parts[1] if len(parts) > 1 else "?"
                sessions.append(f"tmux/{name} ({windows} windows)")
    except Exception:
        pass

    return sessions


def _exec_claude(args):
    """claude 명령 실행 (현재 프로세스를 교체)"""
    claude_path = _find_claude()
    if not claude_path:
        print(c(Colors.RED, "  claude 명령을 찾을 수 없습니다."))
        return

    print()
    os.execvp(claude_path, [claude_path] + args)


def _find_claude():
    """claude CLI 경로 찾기"""
    # which claude
    try:
        result = subprocess.run(
            ["which", "claude"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    # 일반적인 경로들
    common_paths = [
        os.path.expanduser("~/.claude/local/claude"),
        "/usr/local/bin/claude",
        os.path.expanduser("~/.npm/bin/claude"),
    ]
    for p in common_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p

    return None
