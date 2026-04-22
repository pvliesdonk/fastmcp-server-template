# Copier sync + CLAUDE.md parity across MCP services

**Date:** 2026-04-22
**Status:** Draft — pending user review
**Scope:** `fastmcp-server-template` + three consumers (`markdown-vault-mcp`, `scholar-mcp`, `image-generation-mcp`)
**Non-scope:** `fastmcp-pvl-core` library changes; pyproject sentinel refactors (already done); auth overhaul

## 1. Problem statement

Three consumer repos were retrofitted onto `fastmcp-pvl-core` (shared library) and `fastmcp-server-template` (copier template). Two known gaps remain:

1. **The weekly `copier update` workflow has never produced a mergeable or empty PR for any consumer.** Every run either silently exits (no diff) or fails at the `git push` step.
2. **`CLAUDE.md` drift.** The template's sentinel-based hybrid structure (domain-owned vs. template-owned sections) is inconsistently adopted across consumers.

This spec fixes both.

## 2. Root cause analysis

### 2.1 Copier-update push failure

Every failed `copier-update.yml` run terminates with the same GitHub API response:

```
! [remote rejected] copier/update -> copier/update
  (refusing to allow a Personal Access Token to create or update workflow
  `.github/workflows/copier-update.yml` without `workflow` scope)
```

**Why:** the workflow re-renders all `.github/workflows/*.jinja` templates into `.github/workflows/*.yml` on every run. When those files change (including `copier-update.yml` re-rendering *itself*), the push includes workflow file modifications. GitHub's API rejects any PAT push that touches `.github/workflows/` unless the token carries the `workflow` scope. The current `RELEASE_TOKEN` PAT carries `contents:write` + `pull-requests:write` but not `workflow`.

**Evidence:** `image-generation-mcp` run `24772128041` (v1.1.2 update) and run `24772490841` (v1.1.3 update) both failed at the push step with this message. The one "success" run (`24776928650`) only succeeded because `_commit` was already at v1.1.4 — the update was a no-op and no push was attempted.

### 2.2 CLAUDE.md drift

| Repo | Sentinel structure | Domain content wrapping | Template-owned sections present |
|---|---|---|---|
| `fastmcp-server-template` (`CLAUDE.md.jinja`) | full DOMAIN + TEMPLATE-OWNED sentinels | N/A (template) | Conventions, Hard PR Gates, GitHub Review Types, Documentation Discipline, Logging Standard, Config & Customization Contract, Shared Infrastructure (**new, on unmerged `feat/shared-infra-claude-md`**) |
| `markdown-vault-mcp` | full sentinels (on unmerged `refactor/claude-md-sentinels`) | wrapped | Shared Infrastructure deliberately dropped on that branch |
| `scholar-mcp` | **none** | **not wrapped** — domain content ("Key Patterns", task queue) is free-floating | Missing Documentation Discipline, Config & Customization Contract, Shared Infrastructure |
| `image-generation-mcp` | **none** | **not wrapped** — domain "Key Patterns" free-floating | Missing Documentation Discipline, Config & Customization Contract, Shared Infrastructure |

A naive `copier update` against a consumer whose `CLAUDE.md` has no sentinel boundaries produces heavy inline conflict markers across the whole file — which is exactly why the operators have been unable to produce clean PRs even in the few cases where the push would have succeeded.

### 2.3 What is NOT broken

- `pyproject.toml` sentinels (`PROJECT-DEPS-*`, `PROJECT-EXTRAS-*`) are correctly placed in all three consumers.
- `config.py` sentinels (`CONFIG-FIELDS-*`, `CONFIG-FROM-ENV-*`) are correctly placed in all three consumers.
- The template's own `copier-update.yml.jinja` logic (conflict counting, label creation, `--conflict=inline`, `force-with-lease` push, PR body assembly) is correct.
- `template-ci.yml` correctly gates the template with a full smoke render + idempotence check on Python 3.11–3.14.
- `fastmcp-pvl-core` is stable at v1.0.0-rc.1 and not implicated in either failure mode.

## 3. Design

### 3.1 Decision A — token strategy

**Short-term (this work):** re-issue `RELEASE_TOKEN` PAT with `workflow` scope added. Rotate in all four repos via their existing Secrets settings. This is a one-line scope change; the PAT already has write access to the same repos, so the effective blast radius does not change.

**Long-term (follow-up issue, not part of this spec):** migrate to a GitHub App installation token via `actions/create-github-app-token`. Per-repo scoping, automatic rotation, no human-tied identity on automated commits. This is the Dependabot/Renovate pattern but requires registering an app and storing `app-id` + `private-key` secrets in each repo. Out of scope here; tracked as a follow-up.

### 3.2 Decision B — CLAUDE.md migration order

Reject the naive path of "cut v1.1.5 first, let copier resolve everything." A `copier update` against an unsentineled `CLAUDE.md` would produce a wall of conflict markers requiring hand-resolution in every consumer — the same friction that has blocked the team to date.

Instead: **pre-migrate each consumer to the v1.1.4 sentinel shape in isolation, then bump the template.** Three small migration PRs now + one trivial follow-up PR per consumer after the v1.1.5 release.

### 3.3 Phased plan

**Phase 1 — unblock automation**
1. Re-issue `RELEASE_TOKEN` with `workflow` scope; rotate secret in all four repos.
2. Manually dispatch `copier-update.yml` in `image-generation-mcp` as a canary. Confirm a PR lands on branch `copier/update`. (`image-generation-mcp` already has a `chore/copier-update-v1.1.4` branch from earlier attempts — delete that branch before dispatching so the workflow creates a clean one.)
3. File follow-up issue: "migrate copier-update workflow to GitHub App token."

**Phase 2 — CLAUDE.md migration (per-consumer PRs, against template v1.1.4)**
4. `markdown-vault-mcp`: finish review on `refactor/claude-md-sentinels`. The "drop Shared Infrastructure" commit on that branch becomes harmless once template v1.1.5 restores it via copier-update. Merge.
5. `scholar-mcp`: new migration PR that:
   - Wraps existing `## Project Structure` and `## Key Patterns` sections in `<!-- DOMAIN-START -->` / `<!-- DOMAIN-END -->` markers.
   - Adopts the v1.1.4 template-owned block verbatim (Conventions, Hard PR Gates, GitHub Review Types, Documentation Discipline, Logging Standard, Config & Customization Contract).
   - Preserves domain-specific content (async task queue, rate limiter patterns) inside DOMAIN blocks.
6. `image-generation-mcp`: same as scholar-mcp. Preserve the provider-specific "Key Patterns" content inside a DOMAIN block.

Each of these three PRs is a structural move of existing text — no new content, no deletions beyond the explicit "move into sentinel block" operation. CI gate is the existing suite (ruff / mypy / pytest); CLAUDE.md is not code, so the gate's only job is to verify nothing else regressed.

**Phase 3 — release template v1.1.5**
7. Merge `feat/shared-infra-claude-md` → main in `fastmcp-server-template`.
8. Dispatch `template-release.yml` with `bump: patch` → tags `v1.1.5`, cuts GitHub release.
9. Manually dispatch `copier-update.yml` in each of the three consumers (don't wait for Monday cron). Each produces a small PR whose only CLAUDE.md change is inserting the Shared Infrastructure section inside the template-owned block. Merge all three.

**Phase 4 — harden**
10. Verify the weekly cron tick on the next Monday produces zero-diff no-op runs in all three consumers (the "empty PR" case the user specifically called out as never having worked).
11. Add a template-ci assertion that the rendered CLAUDE.md contains both `DOMAIN-START` and `TEMPLATE-OWNED` sentinel markers — cheap regression guard against future structural drift. This goes in the existing `template-ci.yml` after the `pytest` step.

### 3.4 Out of scope (explicitly)

- No changes to `fastmcp-pvl-core`. Drift described here is entirely template-side.
- No pyproject or config.py sentinel changes — already correct.
- No auth rework. GitHub App migration is a tracked follow-up, not a gate.
- No new copier variables. Existing `copier.yml` is sufficient.
- No documentation site (`mkdocs`) changes.
- No CHANGELOG backfill for the consumers; the migration PRs are `refactor:` commits and PSR handles the rest.

## 4. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `workflow`-scoped PAT is lost/leaked | Low | Attacker can modify CI workflows in all three repos | Time-bound the PAT (90 days); migrate to GitHub App as follow-up |
| A consumer has uncommitted edits to CLAUDE.md at migration time | Medium (markdown-vault-mcp has one) | Migration PR merge conflicts with open work | Merge or rebase open CLAUDE.md branches first; only start migration once the file is in known-clean state on main |
| Template v1.1.5 release accidentally bumps minor/major | Low | Wrong tag, requires manual fixup | `template-release.yml` takes explicit `bump` input; pick `patch` |
| Copier `--skip-answered` silently defaults new template vars | Low (v1.1.5 doesn't add vars) | Unnoticed default values land | Already mitigated by the PR body's "skim `.copier-answers.yml` for unexpected new keys" warning |
| Canary run in Phase 1 step 2 still fails | Low | Diagnose from logs; the push error message is explicit | Rollback is a no-op (the branch is automation-only) |

## 5. Success criteria

1. At least one consumer has a merged PR on `copier/update` branch produced by the `copier-update.yml` workflow (cron or `workflow_dispatch` — same code path). Kills the "never produced a mergeable PR" bug.
2. At least one consumer has a successful workflow run that exits with "no changes" and opens no PR. Kills the "never produced an empty PR" bug — the workflow intentionally doesn't open a PR when there's no diff, so a green no-op run *is* the "empty PR" success case.
3. All three consumers have `CLAUDE.md` with both `DOMAIN-START`/`DOMAIN-END` and `TEMPLATE-OWNED` sentinel structure, matching the v1.1.5 template shape.
4. Template v1.1.5 is tagged and released.
5. `template-ci.yml` asserts the rendered CLAUDE.md structure so future drift is caught in the template's own PR gate.

## 6. Test plan

- **Phase 1:** canary workflow dispatch on `image-generation-mcp`. Expected: green run, `copier/update` branch created (or clean no-op if already at latest), PR with `copier` + `dependencies` labels.
- **Phase 2:** for each consumer migration PR, run the existing gate locally (`uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest -x -q`). CLAUDE.md changes don't affect these, so the gate's role is regression-only.
- **Phase 3:** template-ci runs on the v1.1.5 merge PR (full smoke render + idempotence). Post-release, per-consumer workflow dispatch + resulting PR review.
- **Phase 4:** the Monday cron after Phase 3 merges is the first true end-to-end validation.

## 7. Rollback

Each phase is independently revertable:
- Phase 1: revoke the rotated PAT; restore old one. (Old PAT still works for everything except workflow pushes.)
- Phase 2: revert the per-consumer migration PR. CLAUDE.md has no runtime effect.
- Phase 3: `git revert` the v1.1.5 release commit and tag (or just don't roll forward any consumer).
- Phase 4: remove the template-ci assertion if it proves too rigid.
