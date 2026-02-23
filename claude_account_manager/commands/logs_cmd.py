"""
cmd_logs: Token refresh log viewer and exporter
"""
import shutil
from pathlib import Path

from ..ui import c, Colors
from ..logger import LOG_FILE, read_log_lines


def cmd_logs(subcommand=None):
    """토큰 갱신 로그 조회/내보내기

    Args:
        subcommand: None(최근 로그 출력), "export"(데스크탑으로 복사), "path"(경로 출력)
    """
    if subcommand == "path":
        print(str(LOG_FILE))
        return

    if subcommand == "export":
        _export_log()
        return

    # 기본: 최근 로그 출력
    _show_recent_logs()


def _show_recent_logs():
    """최근 로그 50줄 출력"""
    print()
    print(c(Colors.BOLD, "  토큰 갱신 로그 (최근 50줄)"))
    print(c(Colors.DIM, "  " + "─" * 50))

    if not LOG_FILE.exists():
        print(f"  {c(Colors.YELLOW, '로그 파일이 아직 없습니다.')}")
        print(f"  {c(Colors.DIM, '세션 시작 시 자동으로 생성됩니다.')}")
        print()
        return

    lines = read_log_lines(50)
    if not lines:
        print(f"  {c(Colors.YELLOW, '로그가 비어있습니다.')}")
        print()
        return

    for line in lines:
        line = line.rstrip("\n")
        if "ERROR" in line:
            print(f"  {c(Colors.RED, line)}")
        elif "WARN" in line:
            print(f"  {c(Colors.YELLOW, line)}")
        else:
            print(f"  {c(Colors.DIM, line)}")

    print(c(Colors.DIM, "  " + "─" * 50))
    print(f"  {c(Colors.DIM, f'로그 파일: {LOG_FILE}')}")
    print()


def _export_log():
    """로그 파일을 데스크탑으로 복사"""
    print()
    if not LOG_FILE.exists():
        print(f"  {c(Colors.YELLOW, '로그 파일이 아직 없습니다.')}")
        return

    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home()

    dest = desktop / "token-refresh-log.txt"
    try:
        shutil.copy2(LOG_FILE, dest)
        print(f"  {c(Colors.GREEN, '✓')} 로그 파일이 복사되었습니다:")
        print(f"  {c(Colors.CYAN, str(dest))}")
        print()
        print(f"  {c(Colors.DIM, '이 파일을 개발자에게 전달해주세요.')}")
    except Exception as e:
        print(f"  {c(Colors.RED, f'복사 실패: {e}')}")
    print()
