# Upgrading generated projects

Maintainer-facing notes for `copier update` jumps that need one-time manual
steps in generated projects. This file lives only in the template repo (it
is `_exclude`d from renders); link the relevant section from the template
release notes when the release ships.

## v5.0 — release system swap: python-semantic-release → knope release PRs

The v5 template releases through reviewed release pull requests (knope)
instead of PSR's compute-tag-push-at-publish flow. `copier update` delivers
the new machinery (`knope.toml`, `release-prepare.yml`, the rewritten
`release.yml`, `scripts/stamp_manifests.py`, `scripts/promotion_guard.sh`,
the rewritten contract tests) and **deletes** the old
(`[tool.semantic_release]` in `pyproject.toml`, `scripts/bump_manifests.py`,
`scripts/merge_back.sh`, `tests/test_release_contract.py`,
`tests/test_merge_back.py`). Do these by hand, in this order:

1. **Before (or while) running the update: rescue your `DOMAIN-MANIFESTS`
   sentinel content.** Copier deletes template-removed files outright, so
   anything your project added between `scripts/bump_manifests.py`'s
   `DOMAIN-MANIFESTS-HELPERS` / `DOMAIN-MANIFESTS` markers is destroyed
   with the file (recoverable from git history if the update already ran).
   Move that content into the same markers in
   `scripts/stamp_manifests.py`, adapting to its contract: the script
   receives the version as `argv[1]`, runs on stable versions only, must
   raise `StampError` instead of warn-and-continue, and every rewritten
   path must be appended to `stamped` so it is staged into the release
   commit. Drop any `uv.lock`/`pyproject.toml` handling — knope owns those
   natively now.

2. **Normalize `CHANGELOG.md` headings once** (knope writes `## X.Y.Z`,
   PSR wrote `## vX.Y.Z`; keep the `<!-- version list -->` flag line):

   ```bash
   sed -i 's/^## v\([0-9]\)/## \1/' CHANGELOG.md
   ```

   Also reword the seed intro if it names python-semantic-release
   (`CHANGELOG.md` is `_skip_if_exists`, so the update cannot).

3. **Check `RELEASE_TOKEN`.** The same admin-owned fine-grained PAT
   (`contents: write`, `pull_requests: write`, `administration: write`)
   now powers `release-prepare.yml` (prep-branch push + release-PR
   creation) and `release.yml` (tag + GitHub release + port PR). No new
   scopes are needed, but the secret must exist and its owner must hold
   the admin-role ruleset bypass, or release PRs get no CI and tags are
   refused.

4. **Absorb the convention changes.** `perf:` no longer cuts a patch on
   its own — title a genuine performance defect `fix:`, or release with
   the explicit version override. Neither revert form (`revert: ...` or
   `Revert "..."`) reaches `CHANGELOG.md` any more; the `docs/releases/`
   notes page narrates reverts. The changelog shrinks to three sections
   (Breaking Changes / Features / Bug Fixes). Remove any local
   automation, prose, or tests that still expect PSR behavior.

5. **Releasing afterwards:** dispatch **Release Prepare** on the branch to
   release from, review the release PR, merge it — the merge tags and
   publishes. There is no `force`/`finalize` input and no merge-back;
   promotion of an rc series is a plain `channel: stable` prepare, and
   branch releases get an automated bookkeeping port PR to `main`.

Smoke-test the adoption with `knope prepare-release --dry-run` (the
interlock is gone once the PSR block is deleted, so the dry run exercises
the real path), then run the full local gate.
