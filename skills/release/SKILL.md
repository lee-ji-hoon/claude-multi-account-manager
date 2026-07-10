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
git checkout develop
git pull --ff-only origin develop
test -z "$(git status --porcelain)" || { echo "ERROR: develop worktree is not clean" >&2; exit 1; }
```

Stop immediately if checkout, pull, or the clean-tree assertion fails.

### 2. Select a version above every published or installed version

Fetch every remote tag from `origin`, then inspect the version directories in
the local cache at `~/.claude/plugins/cache/lee-ji-hoon/account/`. Parse only
strict `MAJOR.MINOR.PATCH` values, compare their three numeric components, and
find the maximum across both sources. The requested `{version}` must be strict
semver and greater than that maximum. If no version was supplied, report the
maximum and use AskUserQuestion; never infer the next release silently.

After choosing the candidate, verify it with only the Python standard library:

```bash
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
```

### 3. Update all release metadata and changelog

Set the exact same `{version}` in each release artifact:

1. `.claude-plugin/plugin.json`
2. `.claude-plugin/marketplace.json` (`account` entry)
3. `pyproject.toml` (`[project].version`)
4. `CHANGELOG.md` (new dated release entry)

Re-read all three metadata files and stop if any value differs from
`{version}`.

### 4. Run the full release gate

Run every command and stop on the first failure:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
bash tests/test_hooks_shell.sh
bash tests/test_install_shell.sh
bash -n install.sh hooks-handlers/session-start.sh hooks-handlers/prompt-submit.sh
```

Do not commit, push, merge, or tag until the full gate passes.

### 5. Commit and push the tested release on develop

Between the successful gate and release commit, do not pull, checkout, merge,
reset, clean, stash, or edit any file. Only stage the four release files:

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json pyproject.toml CHANGELOG.md
git commit -m "release: v{version}"
git push origin develop
```

Verify that the pushed `develop` HEAD is the release commit before continuing.

### 6. Merge develop into main, then tag main

```bash
git checkout main
git pull --ff-only origin main
git merge develop
```

Confirm the merge succeeded and that the checked-out commit is the intended
main HEAD. Only then create the annotated tag on that exact commit and push the
branch before the tag:

```bash
git tag -a v{version} -m "v{version}" "$(git rev-parse HEAD)"
git push origin main
git push origin v{version}
```

Stop if `git rev-list -n 1 v{version}` differs from `git rev-parse main`.

### 7. Verify the marketplace checkout and exact cache version

Update the marketplace clone and request the plugin update:

```bash
git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" checkout main
git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" pull --ff-only origin main
```

Run `/plugin update account@lee-ji-hoon`, then verify the exact directory
`$HOME/.claude/plugins/cache/lee-ji-hoon/account/{version}` exists. Read only
its `.claude-plugin/plugin.json` version and require an exact `{version}` match;
do not accept a different directory merely because it is the newest cache.

```bash
test -d "$HOME/.claude/plugins/cache/lee-ji-hoon/account/{version}"
python3 - "$HOME/.claude/plugins/cache/lee-ji-hoon/account/{version}/.claude-plugin/plugin.json" "{version}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as manifest:
    actual = json.load(manifest)["version"]
if actual != sys.argv[2]:
    raise SystemExit("exact cache version verification failed")
PY
```

Claude Code must be restarted before using the released plugin.

## Checklist

- [ ] Latest develop is checked out, pulled with `--ff-only`, and clean
- [ ] Requested semver is greater than every remote and cached version
- [ ] All three metadata files equal `{version}` and CHANGELOG is updated
- [ ] Python, both shell suites, and shell syntax gates pass
- [ ] The gated tree is committed and pushed from develop without intervening mutation
- [ ] develop is merged into main before tagging main HEAD
- [ ] main and `v{version}` are pushed in that order
- [ ] Marketplace checkout and exact `{version}` cache are verified
