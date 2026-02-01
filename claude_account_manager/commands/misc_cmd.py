"""
Miscellaneous commands: rename, set_plan, current, help, setup_hook, update, version
"""
import json
import shutil
from pathlib import Path

from ..config import __version__, PACKAGE_NAME
from ..ui import c, Colors
from ..storage import load_index, save_index, get_current_account
from ..version import check_for_updates


def cmd_current():
    """현재 계정 상세 정보 표시"""
    current = get_current_account()
    if not current:
        print("현재 로그인된 계정이 없습니다.")
        return

    print()
    print(c(Colors.BOLD, "  현재 계정"))
    print(c(Colors.DIM, "  " + "─" * 40))

    fields = [
        ("이름", current.get("displayName", "Unknown")),
        ("이메일", current.get("emailAddress", "Unknown")),
        ("조직", current.get("organizationName", "N/A")),
        ("역할", current.get("organizationRole", "N/A")),
        ("UUID", current.get("accountUuid", "N/A")[:20] + "..."),
    ]

    for label, value in fields:
        print(f"  {c(Colors.DIM, label)}: {value}")

    print()


def cmd_rename(account_id, new_name):
    """계정 이름 변경"""
    index = load_index()

    # Find account
    account = None
    for acc in index["accounts"]:
        if acc["id"] == account_id:
            account = acc
            break

    if not account:
        print(f"계정을 찾을 수 없습니다: {account_id}")
        print("\n등록된 계정:")
        for acc in index["accounts"]:
            print(f"   - {acc['id']}: {acc['name']}")
        return False

    old_name = account["name"]
    account["name"] = new_name
    save_index(index)

    print(f"이름 변경 완료: {old_name} → {new_name}")
    return True


def cmd_set_plan(account_id, plan):
    """계정 Plan 수동 설정"""
    valid_plans = ["Free", "Pro", "Team", "Max5", "Max20"]

    # "Max" 입력 시 "Max5"로 자동 변환 (하위 호환)
    if plan == "Max":
        plan = "Max5"
        print(c(Colors.DIM, "  (Max → Max5로 변환됨)"))

    if plan not in valid_plans:
        print(f"유효하지 않은 Plan: {plan}")
        print(f"사용 가능: {', '.join(valid_plans)}")
        return False

    index = load_index()

    # Find account
    account = None
    for acc in index["accounts"]:
        if acc["id"] == account_id:
            account = acc
            break

    if not account:
        print(f"계정을 찾을 수 없습니다: {account_id}")
        return False

    account["plan"] = plan
    save_index(index)

    print(f"Plan 설정 완료: {account['name']} → {plan}")
    return True


def cmd_setup_hook():
    """Claude Code Hook 설정

    ~/.claude/settings.json에 SessionStart hook 추가
    - 기존 Hook 있으면 배열에 추가
    - 백업 생성
    """
    settings_path = Path.home() / ".claude" / "settings.json"

    print()
    print(c(Colors.BOLD, "  Claude Code Hook 설정"))
    print(c(Colors.DIM, "  " + "─" * 50))

    # 1. account_manager.py 경로 결정
    script_path = Path(__file__).parent.parent.parent / "account_manager.py"
    script_path = script_path.resolve()

    # 2. 백업 생성
    if settings_path.exists():
        backup_path = settings_path.with_suffix(".json.bak")
        shutil.copy(settings_path, backup_path)
        print(f"  백업 생성: {c(Colors.DIM, str(backup_path))}")

    # 3. 기존 설정 로드
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            print(f"  {c(Colors.YELLOW, '경고')}: 기존 settings.json 파싱 실패, 새로 생성합니다.")

    # 4. hooks 구조 확인/생성
    if "hooks" not in settings:
        settings["hooks"] = {}

    # 5. SessionStart 배열 확인/생성
    if "SessionStart" not in settings["hooks"]:
        settings["hooks"]["SessionStart"] = []

    session_start = settings["hooks"]["SessionStart"]

    # 6. 이미 auto-add hook 있는지 확인
    for existing in session_start:
        if "auto-add" in existing.get("command", ""):
            print(f"  {c(Colors.GREEN, '✓')} 이미 auto-add Hook이 설정되어 있습니다.")
            print()
            return True

    # 7. 새 Hook 추가
    new_hook = {
        "matcher": "",
        "command": f"python3 {script_path} auto-add"
    }
    session_start.append(new_hook)

    # 8. 저장
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False))

    print(f"  {c(Colors.GREEN, '✓')} Hook 설정 완료")
    print()
    print(f"  {c(Colors.CYAN, '설정 파일')}: {settings_path}")
    print(f"  {c(Colors.CYAN, '실행 명령')}: python3 {script_path} auto-add")
    print()
    print(c(Colors.DIM, "  " + "─" * 50))
    print(f"  {c(Colors.YELLOW, 'Claude Code를 재시작하면 로그인 시 자동으로 계정이 등록됩니다.')}")
    print()
    return True


def cmd_update():
    """최신 버전으로 업데이트"""
    print()
    print(c(Colors.BOLD, "  버전 확인 중..."))

    latest = check_for_updates(silent=False)

    if latest:
        print(f"  새 버전 발견: {c(Colors.GREEN, latest)} (현재: {__version__})")
        print()
        print(f"  {c(Colors.CYAN, '업데이트 명령:')}")
        print(f"    pip install --upgrade {PACKAGE_NAME}")
        print()
    else:
        print(f"  {c(Colors.GREEN, '✓')} 최신 버전입니다: {__version__}")
        print()


def cmd_version():
    """버전 정보 표시"""
    print(f"Claude Account Manager v{__version__}")

    # 업데이트 확인 (백그라운드 캐시 사용)
    latest = check_for_updates(silent=True)
    if latest:
        print(f"  {c(Colors.YELLOW, '⬆')} 새 버전: {latest}")
        print(f"  pip install --upgrade {PACKAGE_NAME}")


def cmd_help():
    """도움말 표시"""
    print(f"""
{c(Colors.BOLD, '  Claude Account Manager')} v{__version__} - 다중 계정 관리
{c(Colors.DIM, '  ' + '─' * 50)}

  {c(Colors.CYAN, '사용법')}: /account [action] [args]

  {c(Colors.CYAN, 'Actions')}:
    list                등록된 계정 목록 + 사용량 (기본값)
    add [name]          현재 로그인된 계정 저장
    export              현재 계정 정보 추출 (다른 컴으로 옮기기)
    import              다른 컴의 계정 가져오기
    switch [id]         계정 전환 (인자 없으면 대화형 선택)
    remove [id]         저장된 계정 삭제
    rename [id] [name]  계정 이름 변경
    set-plan [id] [plan] Plan 수동 설정 (Free/Pro/Team/Max5/Max20)
    auto-add            자동 계정 등록 + 토큰 갱신 (Hook용)
    refresh-all         모든 계정 토큰 갱신
    setup-hook          Claude Code Hook 설정
    check               현재 OAuth 토큰 상태 확인
    update              새 버전 확인
    current             현재 계정 상세 정보
    help                이 도움말 표시

  {c(Colors.CYAN, '예시')}:
    /account add 업무용
    /account switch          {c(Colors.DIM, '# 대화형 선택')}
    /account switch personal
    /account setup-hook      {c(Colors.DIM, '# 로그인 시 자동 등록 Hook 설정')}
    /account check           {c(Colors.DIM, '# 토큰 만료 확인')}
    /account rename joel 조엘
    /account set-plan joel Pro
""")
