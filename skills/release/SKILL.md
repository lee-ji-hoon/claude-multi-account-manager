---
description: Release a new version (version update -> test -> develop commit -> main merge -> tag). Triggered by "release", "deploy", "publish release".
argument-hint: [version] (e.g. 2.2.0)
allowed-tools: [Bash, Read, Edit, AskUserQuestion]
---

# Release

Release one semver version without allowing metadata, tests, branches, tags, or
the installed cache to drift.

## Required sequence

### 1. Prepare a clean, current develop tree

Establish the exact tree that will be edited, tested, and committed before
reading version sources or changing release metadata:

```bash
bash -euo pipefail <<'SH'
git fetch origin '+refs/heads/develop:refs/remotes/origin/develop'
if git show-ref --verify --quiet refs/heads/develop; then
    git checkout develop
else
    git checkout --no-track -b develop origin/develop
fi
git merge --ff-only origin/develop
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/develop)" || { echo "ERROR: local develop differs from origin/develop" >&2; exit 1; }
test -z "$(git status --porcelain)" || { echo "ERROR: develop worktree is not clean" >&2; exit 1; }
SH
```

Stop immediately if fetch, checkout/create, fast-forward merge, remote equality,
or the clean-tree assertion fails. Exact equality rejects a clean local-ahead
develop branch. A newly created develop branch intentionally has no implicit
upstream; the explicit refspec, `origin/develop` merge, and equality check are
the authority without widening `remote.origin.fetch`.

### 2. Select a version above every published or installed version

Fetch every remote tag from `origin`, then inspect the version directories in
the local cache at `~/.claude/plugins/cache/lee-ji-hoon/account/`. Parse only
strict `MAJOR.MINOR.PATCH` values, compare their three numeric components, and
find the maximum across both sources. The requested `{version}` must be strict
semver and greater than that maximum. If no version was supplied, report the
maximum and use AskUserQuestion; never infer the next release silently.

After choosing the candidate, verify it with only the Python standard library:

```bash
bash -euo pipefail <<'SH'
git fetch --tags origin || { echo "ERROR: failed to fetch remote tags" >&2; exit 1; }
python3 - "{version}" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

pattern = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def semver(value):
    if not pattern.fullmatch(value):
        raise SystemExit("version must be strict MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in value.split("."))


requested = sys.argv[1]
requested_semver = semver(requested)
tags = subprocess.check_output(
    ["git", "tag", "--list", "v[0-9]*"], text=True
).splitlines()
remote_versions = [tag[1:] for tag in tags if pattern.fullmatch(tag[1:])]
cache_root = Path.home() / ".claude/plugins/cache/lee-ji-hoon/account"
cache_versions = (
    [entry.name for entry in cache_root.iterdir() if pattern.fullmatch(entry.name)]
    if cache_root.is_dir()
    else []
)
known = remote_versions + cache_versions
highest = max(known, key=semver) if known else None
if highest is not None and requested_semver <= semver(highest):
    raise SystemExit("requested version must exceed the published/cache maximum")
PY
SH
```

### 3. Update all release metadata, changelog, and README impact

Set the exact same `{version}` in each release artifact:

1. `.claude-plugin/plugin.json`
2. `.claude-plugin/marketplace.json` (`account` entry)
3. `pyproject.toml` (`[project].version`)
4. `CHANGELOG.md` (new dated release entry)

The release entry must contain at least one user-visible change bullet and a
`### Documentation` section. Its bullet must either name each updated
`README.md` / `README.ko.md` file, or state
`README 변경 불필요 — <구체적 이유>`. Inspect the actual diff and update both
READMEs whenever install steps, commands, supported providers, UI behavior, or
user-facing configuration changed.

Re-read all three metadata files and stop if any value differs from
`{version}`.

### 4. Run the full release gate

Run every command and stop on the first failure:

```bash
bash -euo pipefail <<'SH'
RELEASE_NOTES_FILE="$(mktemp -t switchboard-release-notes.XXXXXX.md)"
trap 'rm -f "$RELEASE_NOTES_FILE"' EXIT
PREVIOUS_TAG="$(git tag --sort=-version:refname --list 'v[0-9]*' | head -n 1)"
test -n "$PREVIOUS_TAG" || { echo "ERROR: previous release tag not found" >&2; exit 1; }
python3 scripts/release_notes.py "{version}" --base-ref "$PREVIOUS_TAG" --output "$RELEASE_NOTES_FILE"
test -s "$RELEASE_NOTES_FILE"
PYTHON38="$(command -v python3.8 || true)"
if [[ -z "$PYTHON38" ]] && command -v uv >/dev/null 2>&1; then
    PYTHON38="$(uv python find 3.8 2>/dev/null || true)"
fi
test -n "$PYTHON38" && test -x "$PYTHON38" || {
    echo "ERROR: Python 3.8 is required for the release compatibility gate" >&2
    exit 1
}
"$PYTHON38" -m unittest discover -s tests -p 'test_*.py'
"$PYTHON38" -m unittest discover -s prototype/switchboard-menubar/tests -p 'test_*.py'
bash tests/test_hooks_shell.sh
bash tests/test_install_shell.sh
bash -n install.sh hooks-handlers/session-start.sh hooks-handlers/prompt-submit.sh prototype/switchboard-menubar/run.sh prototype/switchboard-menubar/install.sh
APP_PATH="$(prototype/switchboard-menubar/run.sh --build-only | tail -n 1)"
test -d "$APP_PATH"
codesign --verify --deep --strict "$APP_PATH"
APP_ARCHIVE="$(mktemp -t Switchboard-macos.XXXXXX.zip)"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$APP_ARCHIVE"
test -s "$APP_ARCHIVE"
command rm -f "$APP_ARCHIVE"
SH
```

Do not commit, push, merge, or tag until the full gate passes.

### 5. Publish the tested release through develop, main, and the tag

Between the successful gate and release commit, do not pull, checkout, merge,
reset, clean, stash, or edit any file. Stage the release metadata, changelog,
and both READMEs when their impact was recorded:

```bash
bash -euo pipefail <<'SH'
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json pyproject.toml CHANGELOG.md README.md README.ko.md
git commit -m "release: v{version}"
RELEASE_SHA="$(git rev-parse HEAD)"
git push origin develop
git fetch origin '+refs/heads/develop:refs/remotes/origin/develop'
test "$(git rev-parse origin/develop)" = "$RELEASE_SHA" || { echo "ERROR: origin/develop does not equal the release commit" >&2; exit 1; }

git fetch origin '+refs/heads/main:refs/remotes/origin/main'
git checkout main
git merge --ff-only origin/main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" || { echo "ERROR: local main differs from origin/main" >&2; exit 1; }
git merge --no-ff "$RELEASE_SHA" -m "Merge develop: v{version}"
MAIN_SHA="$(git rev-parse HEAD)"
test "$MAIN_SHA" != "$RELEASE_SHA"
test "$(git rev-parse "$MAIN_SHA^2")" = "$RELEASE_SHA"
git merge-base --is-ancestor "$RELEASE_SHA" "$MAIN_SHA"
# Record main HEAD only after it contains the exact release SHA.
git tag -a v{version} -m "v{version}" "$MAIN_SHA"
TAG_SHA="$(git rev-list -n 1 v{version})"
test "$TAG_SHA" = "$MAIN_SHA" || { echo "ERROR: release tag does not point to main HEAD" >&2; exit 1; }
git merge-base --is-ancestor "$RELEASE_SHA" "$TAG_SHA"

git push origin main
git fetch origin '+refs/heads/main:refs/remotes/origin/main'
test "$(git rev-parse origin/main)" = "$MAIN_SHA" || { echo "ERROR: origin/main does not equal the verified main commit" >&2; exit 1; }
git merge-base --is-ancestor "$RELEASE_SHA" "$(git rev-parse origin/main)"
git push origin v{version}
REMOTE_TAG_SHA="$(git ls-remote --tags origin "refs/tags/v{version}^{}" | awk 'NR == 1 {print $1}')"
test "$REMOTE_TAG_SHA" = "$MAIN_SHA" || { echo "ERROR: remote tag does not point to the verified main commit" >&2; exit 1; }
git merge-base --is-ancestor "$RELEASE_SHA" "$REMOTE_TAG_SHA"

# The tag workflow validates the same release contract and publishes GitHub notes.
WORKFLOW_RUN_ID=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
    WORKFLOW_RUN_ID="$(gh run list --repo lee-ji-hoon/ai-account-switcher --workflow release.yml --commit "$MAIN_SHA" --event push --limit 1 --json databaseId --jq '.[0].databaseId // empty')"
    test -n "$WORKFLOW_RUN_ID" && break
    sleep 2
done
test -n "$WORKFLOW_RUN_ID" || { echo "ERROR: release workflow run was not created" >&2; exit 1; }
gh run watch "$WORKFLOW_RUN_ID" --repo lee-ji-hoon/ai-account-switcher --exit-status --compact
test "$(gh release view "v{version}" --repo lee-ji-hoon/ai-account-switcher --json tagName --jq .tagName)" = "v{version}"
SH
```

This publication block is one indivisible fail-fast execution unit. Do not split
it: `RELEASE_SHA` records the gated release commit, each remote ref is checked
after its push, and the tag workflow must publish the generated GitHub Release
before cache verification begins.

### 6. Verify the marketplace checkout and exact cache version

Update the marketplace clone and request the plugin update:

```bash
bash -euo pipefail <<'SH'
test -z "$(git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" status --porcelain)" || { echo "ERROR: marketplace checkout is not clean" >&2; exit 1; }
git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" fetch origin '+refs/heads/main:refs/remotes/origin/main'
git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" checkout main
git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" merge --ff-only origin/main
test "$(git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" rev-parse HEAD)" = "$(git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" rev-parse origin/main)" || { echo "ERROR: local marketplace main differs from origin/main" >&2; exit 1; }
test -z "$(git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" status --porcelain)" || { echo "ERROR: marketplace checkout is not clean" >&2; exit 1; }
SH
```

Run `/plugin update account@lee-ji-hoon`, then verify the exact directory
`$HOME/.claude/plugins/cache/lee-ji-hoon/account/{version}` exists. Read only
its `.claude-plugin/plugin.json` version and require an exact `{version}` match;
do not accept a different directory merely because it is the newest cache.

```bash
bash -euo pipefail <<'SH'
test -d "$HOME/.claude/plugins/cache/lee-ji-hoon/account/{version}"
python3 - "$HOME/.claude/plugins/cache/lee-ji-hoon/account/{version}/.claude-plugin/plugin.json" "{version}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as manifest:
    actual = json.load(manifest)["version"]
if actual != sys.argv[2]:
    raise SystemExit("exact cache version verification failed")
PY
SH
```

Claude Code must be restarted before using the released plugin.

## Checklist

- [ ] Latest develop is fetched by explicit refspec, merged with `--ff-only`, exactly equal to `origin/develop`, and clean
- [ ] Requested semver is greater than every remote and cached version
- [ ] All three metadata files equal `{version}` and CHANGELOG is updated
- [ ] Release notes render successfully and Documentation records the README impact
- [ ] Python, both shell suites, and shell syntax gates pass
- [ ] The gated tree's `RELEASE_SHA` exactly equals the pushed `origin/develop`
- [ ] Local main equals `origin/main` before merging the exact `RELEASE_SHA`
- [ ] Verified main and tag commits contain the exact `RELEASE_SHA`
- [ ] main and `v{version}` are SHA-verified and pushed in that order
- [ ] Tag workflow succeeds and the exact GitHub Release exists
- [ ] Marketplace checkout and exact `{version}` cache are verified
