#!/usr/bin/env bash
# install.sh fail-closed source 설치 회귀 테스트
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0
PYTHON_BIN="$(command -v python3)"
GIT_BIN="$(command -v git)"
SAFE_PATH="$(dirname "$PYTHON_BIN"):$(dirname "$GIT_BIN"):/usr/bin:/bin:/usr/sbin:/sbin"
SENTINEL_SECRET="sentinel-installer-secret-do-not-log"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/account-mgr-installtest.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

PLUGIN_VERSION=$("$PYTHON_BIN" -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' \
    "$REPO_ROOT/.claude-plugin/plugin.json")
EXPECTED_SOURCE_BLOCK="$TMP_ROOT/source-block"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" - \
    "$REPO_ROOT/claude_account_manager/shell_integration.py" \
    "$EXPECTED_SOURCE_BLOCK" <<'PY'
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("shell_integration_for_installer_test", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Path(sys.argv[2]).write_bytes(module.SOURCE_BLOCK.encode("utf-8"))
PY

pass_test() {
    echo "  ok: $1"
}

fail_test() {
    echo "  FAIL: $1"
    FAIL=1
}

assert_equal() {
    local actual="$1" expected="$2" message="$3"
    if [ "$actual" = "$expected" ]; then
        pass_test "$message"
    else
        fail_test "$message (actual=$actual, expected=$expected)"
    fi
}

assert_file_exists() {
    local path="$1" message="$2"
    if [ -f "$path" ]; then
        pass_test "$message"
    else
        fail_test "$message (파일 없음: $path)"
    fi
}

assert_directory_exists() {
    local path="$1" message="$2"
    if [ -d "$path" ]; then
        pass_test "$message"
    else
        fail_test "$message (디렉터리 없음: $path)"
    fi
}

assert_path_absent() {
    local path="$1" message="$2"
    if [ ! -e "$path" ] && [ ! -L "$path" ]; then
        pass_test "$message"
    else
        fail_test "$message (경로가 존재함: $path)"
    fi
}

assert_files_equal() {
    local actual="$1" expected="$2" message="$3"
    if cmp -s "$actual" "$expected"; then
        pass_test "$message"
    else
        fail_test "$message"
    fi
}

assert_file_contains_once_file() {
    local actual="$1" expected="$2" message="$3"
    if "$PYTHON_BIN" - "$actual" "$expected" <<'PY'
import sys
from pathlib import Path

actual = Path(sys.argv[1]).read_bytes()
expected = Path(sys.argv[2]).read_bytes()
raise SystemExit(0 if expected and actual.count(expected) == 1 else 1)
PY
    then
        pass_test "$message"
    else
        fail_test "$message"
    fi
}

assert_file_excludes_secret() {
    local path="$1" message="$2"
    if "$PYTHON_BIN" - "$path" "$SENTINEL_SECRET" <<'PY'
import sys
from pathlib import Path

raise SystemExit(0 if sys.argv[2].encode("utf-8") not in Path(sys.argv[1]).read_bytes() else 1)
PY
    then
        pass_test "$message"
    else
        fail_test "$message"
    fi
}

assert_tree_excludes_secret() {
    local root="$1" message="$2"
    if "$PYTHON_BIN" - "$root" "$SENTINEL_SECRET" <<'PY'
import sys
from pathlib import Path

needle = sys.argv[2].encode("utf-8")
for path in Path(sys.argv[1]).rglob("*"):
    if not path.is_file():
        continue
    try:
        if needle in path.read_bytes():
            raise SystemExit(1)
    except OSError:
        pass
raise SystemExit(0)
PY
    then
        pass_test "$message"
    else
        fail_test "$message"
    fi
}

assert_source_block_once() {
    local rc_path="$1" message="$2"
    if "$PYTHON_BIN" - "$rc_path" "$EXPECTED_SOURCE_BLOCK" <<'PY'
import sys
from pathlib import Path

content = Path(sys.argv[1]).read_bytes()
source_begin = Path(sys.argv[2]).read_bytes().splitlines()[0]
raise SystemExit(0 if content.count(source_begin) == 1 else 1)
PY
    then
        pass_test "$message"
    else
        fail_test "$message"
    fi
}

assert_local_registry() {
    local registry="$1" plugin_dir="$2" message="$3"
    if "$PYTHON_BIN" - "$registry" "$plugin_dir" "$PLUGIN_VERSION" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
entries = data["plugins"]["account@local"]
entry = entries[0]
ok = (
    len(entries) == 1
    and entry["installPath"] == sys.argv[2]
    and entry["version"] == sys.argv[3]
    and "account@lee-ji-hoon" not in data["plugins"]
)
raise SystemExit(0 if ok else 1)
PY
    then
        pass_test "$message"
    else
        fail_test "$message"
    fi
}

file_hash() {
    "$PYTHON_BIN" -c \
        'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' \
        "$1"
}

file_mtime_ns() {
    "$PYTHON_BIN" -c 'import os,sys; print(os.stat(sys.argv[1]).st_mtime_ns)' "$1"
}

file_mode() {
    "$PYTHON_BIN" -c 'import os,stat,sys; print(oct(stat.S_IMODE(os.stat(sys.argv[1]).st_mode)))' "$1"
}

run_installer() {
    local home="$1" stdout_path="$2" stderr_path="$3"
    mkdir -p "$home/tmp"
    env -i \
        HOME="$home" \
        XDG_CONFIG_HOME="$home/.config" \
        PATH="$SAFE_PATH" \
        SHELL=/bin/zsh \
        TMPDIR="$home/tmp" \
        PYTHONDONTWRITEBYTECODE=1 \
        INSTALL_TEST_SECRET="$SENTINEL_SECRET" \
        bash "$REPO_ROOT/install.sh" >"$stdout_path" 2>"$stderr_path"
    INSTALL_STATUS=$?
}

run_installer_with_git_environment() {
    local home="$1" stdout_path="$2" stderr_path="$3"
    shift 3
    mkdir -p "$home/tmp"
    env -i \
        HOME="$home" \
        XDG_CONFIG_HOME="$home/.config" \
        PATH="$SAFE_PATH" \
        SHELL=/bin/zsh \
        TMPDIR="$home/tmp" \
        PYTHONDONTWRITEBYTECODE=1 \
        INSTALL_TEST_SECRET="$SENTINEL_SECRET" \
        "$@" \
        bash "$REPO_ROOT/install.sh" >"$stdout_path" 2>"$stderr_path"
    INSTALL_STATUS=$?
}

assert_install_artifacts() {
    local home="$1"
    local plugin_dir="$home/.claude/plugins/cache/local/account/$PLUGIN_VERSION"
    local relative

    for relative in .claude-plugin hooks hooks-handlers claude_account_manager skills bin; do
        assert_directory_exists "$plugin_dir/$relative" "unsafe 결과 전에도 $relative 복사 완료"
    done
    assert_file_exists "$plugin_dir/account_manager.py" "unsafe 결과 전에도 account_manager.py 복사 완료"
    assert_file_exists "$home/.config/claude-account-manager/shell.sh" "unsafe 결과 전에도 fragment 생성 완료"
    assert_path_absent "$home/.claude/plugins/cache/lee-ji-hoon" "marketplace cache에는 쓰지 않음"
    assert_local_registry \
        "$home/.claude/plugins/installed_plugins.json" \
        "$plugin_dir" \
        "account@local registry가 manifest version과 local path를 사용"
}

echo "[1] symlink rc: fail-closed exit 3 + no-write + 선행 설치 유지"
CASE1="$TMP_ROOT/symlink"
HOME1="$CASE1/home"
mkdir -p "$HOME1"
TARGET1="$CASE1/owned-zshrc"
printf '%s\n' 'export SENTINEL_RC=symlink-target' >"$TARGET1"
ln -s "$TARGET1" "$HOME1/.zshrc"
HASH1_BEFORE=$(file_hash "$TARGET1")
MTIME1_BEFORE=$(file_mtime_ns "$TARGET1")
run_installer "$HOME1" "$CASE1/stdout" "$CASE1/stderr"
HASH1_AFTER=$(file_hash "$TARGET1")
MTIME1_AFTER=$(file_mtime_ns "$TARGET1")
assert_equal "$INSTALL_STATUS" "3" "symlink rc installer exit 3"
assert_equal "$HASH1_AFTER" "$HASH1_BEFORE" "symlink target hash 불변"
assert_equal "$MTIME1_AFTER" "$MTIME1_BEFORE" "symlink target mtime 불변"
assert_file_contains_once_file "$CASE1/stdout" "$EXPECTED_SOURCE_BLOCK" "stdout에 canonical SOURCE_BLOCK을 정확히 한 번 출력"
assert_install_artifacts "$HOME1"

echo "[2] dangling symlink rc: fail-closed exit 3 + no-write"
CASED="$TMP_ROOT/dangling"
HOMED="$CASED/home"
mkdir -p "$HOMED"
TARGETD="$CASED/missing-zshrc"
ln -s "$TARGETD" "$HOMED/.zshrc"
LINKD_BEFORE=$(readlink "$HOMED/.zshrc")
run_installer "$HOMED" "$CASED/stdout" "$CASED/stderr"
LINKD_AFTER=$(readlink "$HOMED/.zshrc")
assert_equal "$INSTALL_STATUS" "3" "dangling symlink rc installer exit 3"
assert_equal "$LINKD_AFTER" "$LINKD_BEFORE" "dangling symlink 자체 불변"
assert_path_absent "$TARGETD" "dangling symlink target을 생성하지 않음"
assert_file_contains_once_file "$CASED/stdout" "$EXPECTED_SOURCE_BLOCK" "dangling symlink 안내도 canonical SOURCE_BLOCK을 정확히 한 번 출력"
assert_install_artifacts "$HOMED"

echo "[3] tracked regular rc: fail-closed exit 3 + no-write"
CASE2="$TMP_ROOT/tracked"
HOME2="$CASE2/home"
mkdir -p "$HOME2"
"$GIT_BIN" init -q "$HOME2"
printf '%s\n' 'export SENTINEL_RC=tracked-regular' >"$HOME2/.zshrc"
"$GIT_BIN" -C "$HOME2" add .zshrc
HASH2_BEFORE=$(file_hash "$HOME2/.zshrc")
MTIME2_BEFORE=$(file_mtime_ns "$HOME2/.zshrc")
run_installer "$HOME2" "$CASE2/stdout" "$CASE2/stderr"
HASH2_AFTER=$(file_hash "$HOME2/.zshrc")
MTIME2_AFTER=$(file_mtime_ns "$HOME2/.zshrc")
assert_equal "$INSTALL_STATUS" "3" "tracked regular rc installer exit 3"
assert_equal "$HASH2_AFTER" "$HASH2_BEFORE" "tracked regular rc hash 불변"
assert_equal "$MTIME2_AFTER" "$MTIME2_BEFORE" "tracked regular rc mtime 불변"
assert_file_contains_once_file "$CASE2/stdout" "$EXPECTED_SOURCE_BLOCK" "tracked rc 안내도 canonical SOURCE_BLOCK을 정확히 한 번 출력"
assert_file_exists "$HOME2/.config/claude-account-manager/shell.sh" "tracked rc 거부 전 fragment 생성 완료"

echo "[4] external Git context tracked rc: fail-closed exit 3 + no-write"
CASEE="$TMP_ROOT/external-git-context"
HOMEE="$CASEE/home"
GIT_DIRE="$CASEE/account.git"
mkdir -p "$HOMEE"
"$GIT_BIN" init --bare -q "$GIT_DIRE"
printf '%s\n' 'export SENTINEL_RC=external-git-context' >"$HOMEE/.zshrc"
env -i HOME="$HOMEE" PATH="$SAFE_PATH" GIT_DIR="$GIT_DIRE" GIT_WORK_TREE="$HOMEE" \
    "$GIT_BIN" add -- .zshrc
env -i HOME="$HOMEE" PATH="$SAFE_PATH" GIT_DIR="$GIT_DIRE" GIT_WORK_TREE="$HOMEE" \
    "$GIT_BIN" ls-files --error-unmatch -- .zshrc >/dev/null 2>&1
assert_equal "$?" "0" "external Git context가 .zshrc를 tracked로 판정"
assert_path_absent "$HOMEE/.git" "fake HOME에는 .git marker가 없음"
"$PYTHON_BIN" -c \
    'import os,sys; t=946684800123456789; os.utime(sys.argv[1], ns=(t,t))' \
    "$HOMEE/.zshrc"
HASHE_BEFORE=$(file_hash "$HOMEE/.zshrc")
MTIMEE_BEFORE=$(file_mtime_ns "$HOMEE/.zshrc")
run_installer_with_git_environment \
    "$HOMEE" "$CASEE/stdout" "$CASEE/stderr" \
    "GIT_DIR=$GIT_DIRE" "GIT_WORK_TREE=$HOMEE"
HASHE_AFTER=$(file_hash "$HOMEE/.zshrc")
MTIMEE_AFTER=$(file_mtime_ns "$HOMEE/.zshrc")
assert_equal "$INSTALL_STATUS" "3" "external Git context tracked rc installer exit 3"
assert_equal "$HASHE_AFTER" "$HASHE_BEFORE" "external Git context tracked rc hash 불변"
assert_equal "$MTIMEE_AFTER" "$MTIMEE_BEFORE" "external Git context tracked rc mtime 불변"
assert_file_contains_once_file "$CASEE/stdout" "$EXPECTED_SOURCE_BLOCK" "external Git context 안내도 canonical SOURCE_BLOCK을 정확히 한 번 출력"
assert_install_artifacts "$HOMEE"

echo "[5] alternate Git index: fail-closed exit 3 + no-write"
CASEI="$TMP_ROOT/alternate-git-index"
HOMEI="$CASEI/home"
GIT_INDEXI="$CASEI/alternate-index"
mkdir -p "$HOMEI"
"$GIT_BIN" init -q "$HOMEI"
printf '%s\n' 'export SENTINEL_RC=alternate-git-index' >"$HOMEI/.zshrc"
"$GIT_BIN" -C "$HOMEI" add -- .zshrc
"$GIT_BIN" -C "$HOMEI" ls-files --error-unmatch -- .zshrc >/dev/null 2>&1
assert_equal "$?" "0" "canonical Git index가 .zshrc를 tracked로 판정"
env -i HOME="$HOMEI" PATH="$SAFE_PATH" GIT_INDEX_FILE="$GIT_INDEXI" \
    "$GIT_BIN" -C "$HOMEI" read-tree --empty
env -i HOME="$HOMEI" PATH="$SAFE_PATH" GIT_INDEX_FILE="$GIT_INDEXI" \
    "$GIT_BIN" -C "$HOMEI" ls-files --error-unmatch -- .zshrc >/dev/null 2>&1
assert_equal "$?" "1" "alternate Git index가 .zshrc를 untracked로 숨김"
"$PYTHON_BIN" -c \
    'import os,sys; t=946684800123456789; os.utime(sys.argv[1], ns=(t,t))' \
    "$HOMEI/.zshrc"
HASHI_BEFORE=$(file_hash "$HOMEI/.zshrc")
MTIMEI_BEFORE=$(file_mtime_ns "$HOMEI/.zshrc")
run_installer_with_git_environment \
    "$HOMEI" "$CASEI/stdout" "$CASEI/stderr" \
    "GIT_INDEX_FILE=$GIT_INDEXI"
HASHI_AFTER=$(file_hash "$HOMEI/.zshrc")
MTIMEI_AFTER=$(file_mtime_ns "$HOMEI/.zshrc")
assert_equal "$INSTALL_STATUS" "3" "alternate Git index rc installer exit 3"
assert_equal "$HASHI_AFTER" "$HASHI_BEFORE" "alternate Git index rc hash 불변"
assert_equal "$MTIMEI_AFTER" "$MTIMEI_BEFORE" "alternate Git index rc mtime 불변"
assert_file_contains_once_file "$CASEI/stdout" "$EXPECTED_SOURCE_BLOCK" "alternate Git index 안내도 canonical SOURCE_BLOCK을 정확히 한 번 출력"
assert_install_artifacts "$HOMEI"

echo "[6] unsafe rc에 exact block 존재: success + no-write"
CASE3="$TMP_ROOT/already"
HOME3="$CASE3/home"
mkdir -p "$HOME3"
TARGET3="$CASE3/owned-zshrc"
"$PYTHON_BIN" - "$TARGET3" "$EXPECTED_SOURCE_BLOCK" <<'PY'
import sys
from pathlib import Path

block = Path(sys.argv[2]).read_bytes()
Path(sys.argv[1]).write_bytes(b"export SENTINEL_RC=before\n" + block + b"export SENTINEL_RC=after\n")
PY
ln -s "$TARGET3" "$HOME3/.zshrc"
HASH3_BEFORE=$(file_hash "$TARGET3")
MTIME3_BEFORE=$(file_mtime_ns "$TARGET3")
run_installer "$HOME3" "$CASE3/stdout" "$CASE3/stderr"
HASH3_AFTER=$(file_hash "$TARGET3")
MTIME3_AFTER=$(file_mtime_ns "$TARGET3")
assert_equal "$INSTALL_STATUS" "0" "exact block이 있는 unsafe rc installer exit 0"
assert_equal "$HASH3_AFTER" "$HASH3_BEFORE" "already symlink target hash 불변"
assert_equal "$MTIME3_AFTER" "$MTIME3_BEFORE" "already symlink target mtime 불변"

echo "[7] regular rc: canonical block 1회 설치 + 재실행 byte/mtime 불변"
CASE4="$TMP_ROOT/regular"
HOME4="$CASE4/home"
mkdir -p "$HOME4"
printf '%s\n' 'export KEEP_UNRELATED=regular-byte-sentinel' >"$HOME4/.zshrc"
chmod 640 "$HOME4/.zshrc"
EXPECTED_RC4="$CASE4/expected-zshrc"
cp "$HOME4/.zshrc" "$EXPECTED_RC4"
cat "$EXPECTED_SOURCE_BLOCK" >>"$EXPECTED_RC4"
run_installer "$HOME4" "$CASE4/stdout-first" "$CASE4/stderr-first"
assert_equal "$INSTALL_STATUS" "0" "regular rc 첫 installer exit 0"
assert_files_equal "$HOME4/.zshrc" "$EXPECTED_RC4" "unrelated bytes 뒤에 canonical block만 추가"
assert_source_block_once "$HOME4/.zshrc" "regular rc에 source block이 정확히 한 번 존재"
assert_equal "$(file_mode "$HOME4/.zshrc")" "0o640" "regular rc mode 보존"
"$PYTHON_BIN" -c \
    'import os,sys; t=946684800123456789; os.utime(sys.argv[1], ns=(t,t))' \
    "$HOME4/.zshrc"
HASH4_BEFORE=$(file_hash "$HOME4/.zshrc")
MTIME4_BEFORE=$(file_mtime_ns "$HOME4/.zshrc")
run_installer "$HOME4" "$CASE4/stdout-second" "$CASE4/stderr-second"
HASH4_AFTER=$(file_hash "$HOME4/.zshrc")
MTIME4_AFTER=$(file_mtime_ns "$HOME4/.zshrc")
assert_equal "$INSTALL_STATUS" "0" "regular rc 두 번째 installer exit 0"
assert_equal "$HASH4_AFTER" "$HASH4_BEFORE" "두 번째 실행에서 regular rc hash 불변"
assert_equal "$MTIME4_AFTER" "$MTIME4_BEFORE" "두 번째 실행에서 regular rc mtime 불변"
assert_source_block_once "$HOME4/.zshrc" "두 번째 실행 후에도 source block 하나"

for output in \
    "$CASE1/stdout" "$CASE1/stderr" \
    "$CASED/stdout" "$CASED/stderr" \
    "$CASE2/stdout" "$CASE2/stderr" \
    "$CASEE/stdout" "$CASEE/stderr" \
    "$CASEI/stdout" "$CASEI/stderr" \
    "$CASE3/stdout" "$CASE3/stderr" \
    "$CASE4/stdout-first" "$CASE4/stderr-first" \
    "$CASE4/stdout-second" "$CASE4/stderr-second"; do
    assert_file_excludes_secret "$output" "installer 출력에 sentinel secret 미노출"
done
assert_tree_excludes_secret "$HOME1" "symlink 설치 결과에 sentinel secret 미저장"
assert_tree_excludes_secret "$HOMED" "dangling symlink 설치 결과에 sentinel secret 미저장"
assert_tree_excludes_secret "$HOME2" "tracked 설치 결과에 sentinel secret 미저장"
assert_tree_excludes_secret "$HOMEE" "external Git context 설치 결과에 sentinel secret 미저장"
assert_tree_excludes_secret "$HOMEI" "alternate Git index 설치 결과에 sentinel secret 미저장"
assert_tree_excludes_secret "$HOME3" "already 설치 결과에 sentinel secret 미저장"
assert_tree_excludes_secret "$HOME4" "regular 설치 결과에 sentinel secret 미저장"

if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "ALL PASS"
    exit 0
fi

echo ""
echo "FAILURES DETECTED"
exit 1
