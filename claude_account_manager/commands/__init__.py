"""
Command router and main entry point
"""
import sys

from .list_cmd import cmd_list
from .add_cmd import cmd_add, cmd_auto_add
from .switch_cmd import cmd_switch
from .remove_cmd import cmd_remove
from .token_cmd import cmd_check, cmd_refresh_all, cmd_refresh_expiring
from .misc_cmd import cmd_current, cmd_rename, cmd_set_plan, cmd_setup_hook, cmd_update, cmd_version, cmd_help
from .import_cmd import cmd_import
from .export_cmd import cmd_export_for_import
from .push_cmd import cmd_push
from .pull_cmd import cmd_pull
from .launch_cmd import cmd_launch
from .logs_cmd import cmd_logs


def main():
    """Main entry point for CLI"""
    args = sys.argv[1:]

    # 버전 옵션 처리
    if args and args[0] in ("--version", "-v", "-V", "version"):
        cmd_version()
        return

    if not args or args[0] in ("list", "ls"):
        cmd_list()
    elif args[0] == "add":
        name = " ".join(args[1:]) if len(args) > 1 else None
        cmd_add(name)
    elif args[0] == "import":
        json_data = " ".join(args[1:]) if len(args) > 1 else None
        cmd_import(json_data)
    elif args[0] == "export":
        cmd_export_for_import()
    elif args[0] == "push":
        cmd_push()
    elif args[0] == "pull":
        source = " ".join(args[1:]) if len(args) > 1 else None
        cmd_pull(source)
    elif args[0] == "launch":
        extra = args[1:] if len(args) > 1 else None
        cmd_launch(extra)
    elif args[0] == "switch":
        account_id = args[1] if len(args) > 1 else None
        cmd_switch(account_id)
    elif args[0] in ("remove", "rm", "delete"):
        account_id = args[1] if len(args) > 1 else None
        cmd_remove(account_id)
    elif args[0] == "rename":
        if len(args) < 3:
            print("사용법: /account rename [계정ID] [새이름]")
            print("예: /account rename joel 조엘")
            return
        cmd_rename(args[1], " ".join(args[2:]))
    elif args[0] == "set-plan":
        if len(args) < 3:
            print("사용법: /account set-plan [계정ID] [Plan]")
            print("Plan: Free, Pro, Team, Max5, Max20")
            print("예: /account set-plan joel Pro")
            return
        cmd_set_plan(args[1], args[2])
    elif args[0] == "auto-add":
        cmd_auto_add()
        cmd_refresh_all()  # 모든 계정 토큰 갱신
        sys.exit(0)  # Hook은 항상 0으로 종료
    elif args[0] == "refresh-all":
        count = cmd_refresh_all()
        print(f"갱신된 계정: {count}개")
        sys.exit(0)
    elif args[0] == "refresh-expiring":
        hours = int(args[1]) if len(args) > 1 else 1
        count = cmd_refresh_expiring(hours)
        if count > 0:
            print(f"만료 임박 토큰 갱신: {count}개")
        sys.exit(0)
    elif args[0] == "setup-hook":
        cmd_setup_hook()
    elif args[0] == "logs":
        subcommand = args[1] if len(args) > 1 else None
        cmd_logs(subcommand)
    elif args[0] == "check":
        cmd_check()
    elif args[0] == "update":
        cmd_update()
    elif args[0] == "current":
        cmd_current()
    elif args[0] in ("help", "-h", "--help"):
        cmd_help()
    else:
        print(f"알 수 없는 명령: {args[0]}")
        print("/account help 로 사용법을 확인하세요.")


__all__ = [
    "main",
    "cmd_list",
    "cmd_add",
    "cmd_auto_add",
    "cmd_switch",
    "cmd_remove",
    "cmd_import",
    "cmd_export_for_import",
    "cmd_push",
    "cmd_pull",
    "cmd_launch",
    "cmd_logs",
    "cmd_check",
    "cmd_refresh_all",
    "cmd_refresh_expiring",
    "cmd_current",
    "cmd_rename",
    "cmd_set_plan",
    "cmd_setup_hook",
    "cmd_update",
    "cmd_version",
    "cmd_help",
]
