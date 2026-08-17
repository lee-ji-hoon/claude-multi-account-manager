# Switchboard release contract

This is the AI-neutral entrypoint for every release, regardless of which agent performs it. The executable source of truth is `scripts/release_notes.py`; the complete branch, test, tag, and cache sequence is `skills/release/SKILL.md`.

Before publishing a version:

1. Update the three version sources and add an exact dated `CHANGELOG.md` section.
2. Add at least one user-visible change bullet.
3. Add `### Documentation` with one bullet that either names the updated `README.md` / `README.ko.md`, or says `README 변경 불필요 — <구체적 이유>`.
4. Find the previous release tag and run `python3 scripts/release_notes.py <version> --base-ref <previous-tag> --output /tmp/switchboard-release-notes.md`, then run the full test gate from the release skill. User-facing changes fail unless both README files are changed and named in the release notes.
5. Build, ad-hoc sign, verify, and archive `Switchboard.app` before publishing the tag.
6. Publish the verified `main` commit and `v<version>` tag using the release skill sequence. The workflow creates the GitHub Release only after the macOS archive exists, and attaches `Switchboard-macos.zip` in the same create operation.

The validator requires `--base-ref`; every AI therefore has to compare the real release diff instead of relying on a prose-only README declaration. The tag-triggered GitHub workflow reruns the same validator and creates the GitHub Release from the rendered changelog section. Missing notes, inconsistent versions, placeholders, or a missing README impact declaration prevent release publication.
