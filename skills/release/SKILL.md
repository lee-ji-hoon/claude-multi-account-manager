---
description: Release a new version (version update -> commit -> tag -> merge to main -> push). Triggered by "release", "deploy", "publish release".
argument-hint: [version] (e.g. 2.2.0)
allowed-tools: [Bash, Read, Edit, AskUserQuestion]
---

# Release

Releases a new version.

## Required Rules

1. **Version format**: Must follow semver (MAJOR.MINOR.PATCH)
2. **Branch strategy**: Merge develop -> main, then tag
3. **Marketplace cache**: Must verify update

## Instructions

### 1. Determine Version

If no version is provided as an argument:
- Check current version: `cat .claude-plugin/plugin.json | grep version`
- Check latest cached version: `ls ~/.claude/plugins/cache/lee-ji-hoon/account/`
- Use AskUserQuestion to get the new version

**Important**: The new version must be higher than all cached versions (semver comparison)

### 2. Update plugin.json Version

Use the Edit tool to modify the version field in `.claude-plugin/plugin.json`

### 3. Commit and Create Tag

```bash
git add -A
git commit -m "release: v{version}

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git tag -a v{version} -m "v{version}"
git push origin develop
```

### 4. Merge to main Branch (Required!)

```bash
git checkout main
git merge develop
git push origin main
git push origin v{version}
git checkout develop
```

### 5. Verify Marketplace Cache Update

```bash
cd ~/.claude/plugins/marketplaces/lee-ji-hoon && git pull origin main
```

### 6. Completion Notice

- Claude Code restart required
- Run `/plugin update account@lee-ji-hoon`

## Checklist

- [ ] Update plugin.json version
- [ ] Commit on develop branch
- [ ] Create tag (v{version})
- [ ] **Merge to main branch** (important!)
- [ ] Push main + push tag
- [ ] Verify marketplace cache update
