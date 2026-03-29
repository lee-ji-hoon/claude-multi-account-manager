"""
cmd_check, cmd_refresh_all, cmd_refresh_expiring: Token management commands
"""
import fcntl
import json
import os

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors
from ..storage import load_index, save_index, get_current_account
from ..keychain import get_keychain_credential
from ..token import TokenStatus, check_token_status, refresh_access_token, is_token_expiring_soon, is_token_fresh, is_credential_valid, classify_refresh_error, RefreshError
from ..api import _fetch_usage_from_api
from ..account import detect_plan_from_credential, is_same_account
from ..logger import log, log_token_info


def _safe_refresh_credential(credential_path, acc_id, skip_fresh_check=False):
    """파일 락을 사용하여 credential을 안전하게 갱신

    동시에 여러 프로세스가 같은 refresh token을 사용하는 것을 방지합니다.
    Non-blocking 락을 사용하여 다른 프로세스가 갱신 중이면 스킵합니다.

    Args:
        credential_path: credential 파일 경로 (Path 객체)
        acc_id: 계정 ID (로깅용)
        skip_fresh_check: True이면 토큰 신선도 체크를 건너뛰고 항상 갱신 시도

    Returns:
        tuple: (new_credential or None, error_message or None)
    """
    lock_path = credential_path.parent / f"{credential_path.name}.lock"
    lock_fd = None

    try:
        # 1. 락 파일 열기 및 non-blocking 락 획득 시도
        lock_fd = open(lock_path, "w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            # 다른 프로세스가 갱신 중 → 스킵
            log("INFO", f"[{acc_id}] 락 획득 실패 → 다른 프로세스 갱신 중")
            return None, "skip:locked"

        # 2. 락 획득 후 credential 파일 다시 읽기 (다른 프로세스가 이미 갱신했을 수 있음)
        try:
            credential = json.loads(credential_path.read_text())
        except (json.JSONDecodeError, IOError):
            return None, "credential 파일 읽기 실패"

        # 3. 토큰 신선도 체크 (잔여 > 7시간이면 최근 갱신된 것)
        if not skip_fresh_check:
            if is_token_fresh(credential):
                log("INFO", f"[{acc_id}] 토큰 신선 → 스킵")
                return credential, "skip:fresh"

        # 4. refresh_access_token 호출
        log_token_info(acc_id, credential, "갱신 전 ")
        new_credential, error = refresh_access_token(credential)

        if new_credential:
            # 5. 성공 → 파일 저장 (fsync로 원자적 기록 보장)
            with open(credential_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(new_credential, indent=2, ensure_ascii=False))
                f.flush()
                os.fsync(f.fileno())
            os.chmod(credential_path, 0o600)
            log_token_info(acc_id, new_credential, "갱신 후 ")
            return new_credential, None

        # 6. 실패 → 파일 다시 읽기 (다른 프로세스가 갱신했을 수 있음)
        log("WARN", f"[{acc_id}] 갱신 실패: {error}")
        try:
            reread_credential = json.loads(credential_path.read_text())
            if is_token_fresh(reread_credential):
                log("INFO", f"[{acc_id}] 실패했지만 파일 토큰 신선 → 다른 프로세스가 갱신한 듯")
                return reread_credential, "skip:fresh_after_fail"
        except (json.JSONDecodeError, IOError):
            pass

        # 에러 분류: 영구 실패면 접두사 마킹
        error_type = classify_refresh_error(error)
        if error_type == RefreshError.PERMANENT:
            return None, f"permanent:{error}"
        return None, error

    finally:
        # 락 해제 및 정리
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass
            try:
                lock_path.unlink(missing_ok=True)
            except Exception:
                pass


def cmd_check():
    """현재 OAuth 토큰 상태 확인"""
    print()
    print(c(Colors.BOLD, "  OAuth 토큰 상태 확인"))
    print(c(Colors.DIM, "  " + "─" * 50))

    current = get_current_account()
    current_email = current.get("emailAddress", "")

    if not current_email:
        print(f"  {c(Colors.YELLOW, '현재 로그인된 계정이 없습니다.')}")
        print()
        return

    print(f"  계정: {current_email}")
    print()

    # 현재 토큰 상태 확인
    token_status, message = check_token_status()

    if token_status == TokenStatus.VALID:
        print(f"  {c(Colors.GREEN, '✓')} 토큰 상태: {c(Colors.GREEN, '유효')}")
        # 추가로 사용량 정보도 표시
        usage = _fetch_usage_from_api()
        if usage:
            print()
            if usage["fiveHour"] is not None:
                print(f"  현재 세션 사용량: {usage['fiveHour']}%")
            if usage["sevenDay"] is not None:
                print(f"  주간 사용량: {usage['sevenDay']}%")
    elif token_status == TokenStatus.REFRESHED:
        print(f"  {c(Colors.GREEN, '✓')} 토큰 상태: {c(Colors.GREEN, '자동 갱신됨')}")
        print(f"  {c(Colors.CYAN, '→')} {message}")
        # 갱신 후 사용량 정보 표시
        usage = _fetch_usage_from_api()
        if usage:
            print()
            if usage["fiveHour"] is not None:
                print(f"  현재 세션 사용량: {usage['fiveHour']}%")
            if usage["sevenDay"] is not None:
                print(f"  주간 사용량: {usage['sevenDay']}%")
    elif token_status == TokenStatus.EXPIRED:
        print(f"  {c(Colors.RED, '✗')} 토큰 상태: {c(Colors.RED, '만료됨')}")
        print()
        print(f"  {c(Colors.YELLOW, '해결 방법:')}")
        print(f"    1. Claude Code에서 {c(Colors.CYAN, '/logout')} 실행")
        print(f"    2. {c(Colors.CYAN, '/login')} 으로 재로그인")
        print(f"    3. {c(Colors.CYAN, 'account add')} 로 토큰 다시 저장")
    elif token_status == TokenStatus.INVALID:
        print(f"  {c(Colors.RED, '✗')} 토큰 상태: {c(Colors.RED, '무효')}")
        print()
        print(f"  {c(Colors.YELLOW, '해결 방법:')}")
        print(f"    1. Claude Code에서 {c(Colors.CYAN, '/logout')} 실행")
        print(f"    2. {c(Colors.CYAN, '/login')} 으로 재로그인")
        print(f"    3. {c(Colors.CYAN, 'account add')} 로 토큰 다시 저장")
    elif token_status == TokenStatus.NO_TOKEN:
        print(f"  {c(Colors.YELLOW, '!')} 토큰 상태: {c(Colors.YELLOW, '토큰 없음')}")
        print()
        print(f"  {c(Colors.DIM, 'Keychain에 저장된 토큰이 없습니다.')}")
    else:
        print(f"  {c(Colors.YELLOW, '?')} 토큰 상태: {c(Colors.YELLOW, '확인 불가')}")
        if message:
            print(f"  {c(Colors.DIM, message)}")

    print(c(Colors.DIM, "  " + "─" * 50))
    print()


def _auto_migrate(index, current):
    """세션 시작 시 자동 마이그레이션

    레거시 필드 정리 및 누락된 credential 파일 복구.
    """
    migrated = False

    for acc in index["accounts"]:
        # v2.3.0: refreshBlocked 레거시 필드 제거
        if acc.get("refreshBlocked") is not None or acc.get("refreshBlockedAt") is not None:
            acc.pop("refreshBlocked", None)
            acc.pop("refreshBlockedAt", None)
            migrated = True
            log("INFO", f"[migrate] {acc['id']}: refreshBlocked 레거시 필드 제거")

        # credentialFile이 null인 계정 복구
        if not acc.get("credentialFile"):
            cred_file = f"credential_{acc['id']}.json"
            cred_path = ACCOUNTS_DIR / cred_file

            if current and is_same_account(acc, current):
                # 현재 활성 계정: Keychain에서 credential 저장
                keychain_cred = get_keychain_credential()
                if keychain_cred and is_credential_valid(keychain_cred):
                    with open(cred_path, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(keychain_cred, indent=2, ensure_ascii=False))
                        f.flush()
                        os.fsync(f.fileno())
                    os.chmod(cred_path, 0o600)
                    acc["credentialFile"] = cred_file
                    migrated = True
                    log("INFO", f"[migrate] {acc['id']}: credential 파일 생성 (keychain)")
                    print(f"[migrate] {acc['id']}: credential 저장됨")
            elif cred_path.exists():
                # 비활성 계정: 디스크에 파일이 있으면 index만 복구
                acc["credentialFile"] = cred_file
                migrated = True
                log("INFO", f"[migrate] {acc['id']}: credentialFile index 복구")
                print(f"[migrate] {acc['id']}: credentialFile 복구됨")

    if migrated:
        save_index(index)


def cmd_refresh_all():
    """모든 등록된 계정의 토큰 갱신 (Hook용, 비대화형)

    세션 시작 시 모든 계정을 무조건 갱신하여:
    - 장기간 미사용 계정의 토큰 만료 방지
    - 세션 중간에 토큰 만료되는 상황 방지
    - 모든 계정이 항상 최신 토큰 유지

    Returns:
        int: 갱신 성공한 계정 수
    """
    index = load_index()
    if not index["accounts"]:
        log("INFO", "cmd_refresh_all: 등록된 계정 없음")
        return 0

    # 자동 마이그레이션 (v2.2.6+: keychain -a 수정 후 복구)
    current = get_current_account()
    _auto_migrate(index, current)
    # 마이그레이션 후 index 다시 읽기 (save 되었을 수 있음)
    index = load_index()

    log("INFO", f"=== SessionStart: cmd_refresh_all 시작 (계정 {len(index['accounts'])}개) ===")
    refreshed_count = 0
    skipped_count = 0
    error_count = 0

    for acc in index["accounts"]:
        credential_file = acc.get("credentialFile")
        if not credential_file:
            continue

        credential_path = ACCOUNTS_DIR / credential_file

        # 현재 로그인된 계정 처리
        if current and is_same_account(acc, current):
            # Keychain에서 최신 토큰 가져와서 저장
            current_credential = get_keychain_credential()
            if current_credential:
                # 유효성 검증: 불완전한 credential 저장 방지
                if not is_credential_valid(current_credential):
                    log("WARN", f"[{acc['id']}] Keychain credential 불완전 → 파일 저장 스킵")
                    skipped_count += 1
                    continue

                lock_path = credential_path.parent / f"{credential_path.name}.lock"
                lock_fd = None
                locked = False
                try:
                    lock_fd = open(lock_path, "w")
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        locked = True
                    except (IOError, OSError):
                        log("WARN", f"[{acc['id']}] 현재 계정 credential 락 획득 실패 → 스킵")

                    if locked:
                        with open(credential_path, 'w', encoding='utf-8') as f:
                            f.write(json.dumps(current_credential, indent=2, ensure_ascii=False))
                            f.flush()
                            os.fsync(f.fileno())
                        os.chmod(credential_path, 0o600)
                finally:
                    if lock_fd is not None:
                        try:
                            fcntl.flock(lock_fd, fcntl.LOCK_UN)
                            lock_fd.close()
                        except Exception:
                            pass
                        try:
                            lock_path.unlink(missing_ok=True)
                        except Exception:
                            pass

                # Plan도 갱신
                detected_plan = detect_plan_from_credential(current_credential)
                acc["plan"] = detected_plan

                refreshed_count += 1
                log_token_info(acc["id"], current_credential, "현재 계정 저장 ")
                print(f"[refresh] {acc['id']}: 현재 계정 토큰 저장됨 [{detected_plan}]")
            else:
                log("WARN", f"[{acc['id']}] 현재 계정이지만 Keychain credential 없음")
            continue

        # 다른 계정은 안전한 갱신 (파일 락 + 신선도 체크)
        if not credential_path.exists():
            log("WARN", f"[{acc['id']}] credential 파일 없음: {credential_file}")
            continue

        new_credential, error = _safe_refresh_credential(credential_path, acc["id"])

        if error and error.startswith("skip:"):
            # 스킵된 경우 (락 획득 실패 또는 이미 신선한 토큰)
            skipped_count += 1
            reason = error.split(":", 1)[1]
            if reason == "locked":
                print(f"[refresh] {acc['id']}: 다른 프로세스 갱신 중 → 스킵")
            elif reason in ("fresh", "fresh_after_fail"):
                # 이미 신선한 토큰 → Plan 업데이트만
                if new_credential:
                    detected_plan = detect_plan_from_credential(new_credential)
                    acc["plan"] = detected_plan
                print(f"[refresh] {acc['id']}: 최근 갱신됨 → 스킵 [{acc.get('plan', '?')}]")
            continue

        if new_credential and not error:
            # Plan도 갱신
            detected_plan = detect_plan_from_credential(new_credential)
            acc["plan"] = detected_plan

            refreshed_count += 1
            print(f"[refresh] {acc['id']}: 토큰 갱신됨 [{detected_plan}]")
        elif error:
            actual_error = error[len("permanent:"):] if error.startswith("permanent:") else error
            is_permanent = error.startswith("permanent:")
            log("ERROR", f"[{acc['id']}] 갱신 실패 ({'영구' if is_permanent else '일시'}): {actual_error}")
            if is_permanent:
                print(f"[refresh] {acc['id']}: 토큰 만료 - 해당 계정으로 재로그인 후 /account:add 필요")
            else:
                print(f"[refresh] {acc['id']}: 갱신 실패 - {actual_error}")
            error_count += 1

    # index 저장 (Plan 정보 갱신)
    save_index(index)

    log("INFO", f"cmd_refresh_all 완료 (갱신: {refreshed_count}, 스킵: {skipped_count}, 실패: {error_count})")
    return refreshed_count


def cmd_refresh_expiring(hours=1):
    """만료 임박 토큰만 갱신 (UserPromptSubmit Hook용)

    세션 중간에 토큰 만료를 방지하기 위해,
    만료 N시간 이내인 토큰만 선택적으로 갱신합니다.

    Args:
        hours: 만료 임박 기준 시간 (기본 1시간)

    Returns:
        int: 갱신 성공한 계정 수
    """
    index = load_index()
    if not index["accounts"]:
        return 0

    log("INFO", f"--- PromptSubmit: cmd_refresh_expiring 시작 (기준: {hours}시간) ---")
    refreshed_count = 0
    expiring_found = 0
    current = get_current_account()

    # 현재 계정: Keychain → 파일 credential 동기화
    # Claude CLI가 자체적으로 토큰을 갱신하면 Keychain만 업데이트됨
    # account manager의 파일은 stale 상태가 됨 → 여기서 동기화 (이슈 #12)
    if current:
        for acc in index["accounts"]:
            if is_same_account(acc, current):
                credential_file = acc.get("credentialFile")
                if credential_file:
                    credential_path = ACCOUNTS_DIR / credential_file
                    kc_cred = get_keychain_credential()
                    if kc_cred and is_credential_valid(kc_cred):
                        kc_expires = kc_cred.get("claudeAiOauth", {}).get("expiresAt", 0)
                        try:
                            file_cred = json.loads(credential_path.read_text())
                            file_expires = file_cred.get("claudeAiOauth", {}).get("expiresAt", 0)
                        except (json.JSONDecodeError, IOError, FileNotFoundError):
                            file_expires = 0
                        if kc_expires > file_expires:
                            try:
                                with open(credential_path, 'w', encoding='utf-8') as f:
                                    f.write(json.dumps(kc_cred, indent=2, ensure_ascii=False))
                                    f.flush()
                                    os.fsync(f.fileno())
                                os.chmod(credential_path, 0o600)
                                log("INFO", f"[{acc['id']}] Keychain → 파일 credential 동기화")
                            except Exception as e:
                                log("WARN", f"[{acc['id']}] credential 동기화 실패: {e}")
                break

    for acc in index["accounts"]:
        # 현재 계정은 스킵 (이미 활성 상태)
        if current and is_same_account(acc, current):
            continue

        credential_file = acc.get("credentialFile")
        if not credential_file:
            continue

        credential_path = ACCOUNTS_DIR / credential_file
        if not credential_path.exists():
            continue

        # 만료 임박 여부 먼저 확인 (락 획득 전 빠른 필터링)
        try:
            credential = json.loads(credential_path.read_text())
        except (json.JSONDecodeError, IOError):
            continue

        if not is_token_expiring_soon(credential, hours=hours):
            continue

        expiring_found += 1
        log_token_info(acc["id"], credential, "만료 임박 감지 ")

        # 안전한 갱신 (파일 락 + 신선도 체크)
        new_credential, error = _safe_refresh_credential(credential_path, acc["id"])

        if error and error.startswith("skip:"):
            continue

        if new_credential and not error:
            detected_plan = detect_plan_from_credential(new_credential)
            acc["plan"] = detected_plan

            refreshed_count += 1
            print(f"[refresh] {acc['id']}: 만료 임박 토큰 갱신됨 [{detected_plan}]")
        elif error:
            actual_error = error[len("permanent:"):] if error.startswith("permanent:") else error
            log("ERROR", f"[{acc['id']}] 만료 임박 갱신 실패: {actual_error}")

    if refreshed_count > 0:
        save_index(index)

    if expiring_found == 0:
        log("INFO", "cmd_refresh_expiring: 만료 임박 계정 없음")
    else:
        log("INFO", f"cmd_refresh_expiring 완료 (감지: {expiring_found}, 갱신: {refreshed_count})")

    return refreshed_count
