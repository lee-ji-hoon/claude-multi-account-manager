"""
UI utilities: colors, formatting, progress bars
"""
import os
import sys


class Colors:
    """ANSI 색상 코드"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


def supports_color():
    """터미널이 색상을 지원하는지 확인"""
    return sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


USE_COLOR = supports_color()


def c(color, text):
    """색상 적용 (지원 시에만)"""
    if USE_COLOR:
        return f"{color}{text}{Colors.RESET}"
    return text


def format_tokens(n):
    """토큰 수를 읽기 쉽게 포맷"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def make_progress_bar(percentage, width=20, filled_char="█", empty_char="░"):
    """아스키 진행 막대 생성"""
    percentage = max(0, min(100, percentage))
    filled = int(width * percentage / 100)
    empty = width - filled

    bar = filled_char * filled + empty_char * empty

    # 색상 적용 (사용량에 따라)
    if percentage >= 90:
        return c(Colors.RED, bar)
    elif percentage >= 70:
        return c(Colors.YELLOW, bar)
    elif percentage >= 50:
        return c(Colors.CYAN, bar)
    else:
        return c(Colors.GREEN, bar)


def format_time_remaining(hours, minutes):
    """남은 시간 포맷"""
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
