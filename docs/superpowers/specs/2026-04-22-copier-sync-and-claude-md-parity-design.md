# Copier sync + CLAUDE.md parity across MCP services

**Date:** 2026-04-22
**Status:** Draft — pending user review
**Scope:** `fastmcp-server-template` + three consumers (`markdown-vault-mcp`, `scholar-mcp`, `image-generation-mcp`)
**Non-scope:** `fastmcp-pvl-core` library changes; pyproject sentinel refactors (already done); auth overhaul

## 1. Problem statement

Three consumer repos were retrofitted onto `fastmcp-pvl-core` (shared library) and `fastmcp-server-template` (copier template). Known gaps remain:

1. **The weekly `copier update` workflow has never produced a PR that could merge without hand-intervention.** History:
   - Early runs failed outright at `git push` (PAT scope issue — **since resolved**; `RELEASE_TOKEN` now carries `workflow` scope).
   - The one truly automated PR that did open — `image-generation-mcp` PR #192 on `copier/update` — arrived CI-red because the copier-regenerated `tests/test_smoke.py` imported `make_server` from `server.py`, but the consumer was still mid-rebase (`mcp_server.py` + `create_server` alias). The operator had to push four hand-fix commits to get it green.
   - `scholar-mcp` PR #156 on `copier/update` was opened then closed unmerged. `markdown-vault-mcp` has never had a bot-opened `copier/update` PR at all.
   - No consumer has ever experienced the happy-path steady state: a green no-op cron tick that opens no PR.
2. **`CLAUDE.md` drift.** The template's sentinel-based hybrid structure (domain-owned vs. template-owned sections) is inconsistently adopted across consumers. `scholar-mcp` and `image-generation-mcp` have no sentinels at all, so any `copier update` touching CLAUDE.md produces a wall of inline conflict markers.
3. **Two half-landed refactor branches are blocking steady state:** `fastmcp-server-template/feat/shared-infra-claude-md` (Shared Infrastructure section + not-yet-released) and `markdown-vault-mcp/refactor/claude-md-sentinels` (MV's sentinel migration, unmerged). Until both land, no copier-update cycle will look clean.

This spec fixes all three.

## 2. Root cause analysis

### 2.1 Copier-update push failure — ROOT CAUSE RESOLVED

Earlier failed `copier-update.yml` runs terminated with:

```
! [remote rejected] copier/update -> copier/update
  (refusing to allow a Personal Access Token to create or update workflow
  `.github/workflows/copier-update.yml` without `workflow` scope)
```

**Why:** the workflow re-renders all `.github/workflows/*.jinja` templates into `.github/workflows/*.yml` on every run, including `copier-update.yml` re-rendering itself. GitHub's API rejects any PAT push that touches `.github/workflows/` unless the token carries the `workflow` scope.

**Status:** `RELEASE_TOKEN` has been rotated with `workflow` scope across all four repos. This class of failure is fixed. Post-rotation, `image-generation-mcp` successfully ran the workflow and bot-opened PR #192 on `copier/update` — which proves the push path works end-to-end.

### 2.2 Unmergeable bot PR — the "incomplete rebase meets regenerated scaffold" class

`image-generation-mcp` PR #192 (the first successful bot-opened PR) was unmergeable on arrival because copier regenerated `tests/test_smoke.py` importing `make_server` from `image_generation_mcp.server`, but the consumer's retrofit had left the module at `mcp_server.py` with a `create_server = make_server` backcompat alias. Fixing this required four manual commits on top of the bot's commit — a full `git mv` of the module plus 15-file import sweep.

That specific failure is now historical: IG's `server.py` + `make_server` transition is finished (confirmed: `ls src/image_generation_mcp/server.py` present, `test_smoke.py` imports the canonical path). `scholar-mcp` and `markdown-vault-mcp` already have canonical `server.py` + `make_server` + canonical `test_smoke.py` shape. All template-canonical infrastructure files (`Dockerfile`, `compose.yml`, `docker-entrypoint.sh`, `packaging/nfpm.yaml`, `packaging/mcpb/*`, `scripts/bump_manifests.py`, `server.json`, `codecov.yml`) are present in all three consumers. **The rebase-level drift is substantively done.**

What remains brittle: the *next* bot PR will still produce a messy diff whenever the template changes any file for which the consumer lacks sentinel boundaries. That's almost entirely a CLAUDE.md problem now — see §2.3.

### 2.3 CLAUDE.md drift

| Repo | Sentinel structure | Domain content wrapping | Template-owned sections present |
|---|---|---|---|
| `fastmcp-server-template` (`CLAUDE.md.jinja`) | full DOMAIN + TEMPLATE-OWNED sentinels | N/A (template) | Conventions, Hard PR Gates, GitHub Review Types, Documentation Discipline, Logging Standard, Config & Customization Contract, Shared Infrastructure (**new, on unmerged `feat/shared-infra-claude-md`**) |
| `markdown-vault-mcp` | full sentinels (on unmerged `refactor/claude-md-sentinels`) | wrapped | Shared Infrastructure deliberately dropped on that branch |
| `scholar-mcp` | **none** | **not wrapped** — domain content ("Key Patterns", task queue) is free-floating | Missing Documentation Discipline, Config & Customization Contract, Shared Infrastructure |
| `image-generation-mcp` | **none** | **not wrapped** — domain "Key Patterns" free-floating | Missing Documentation Discipline, Config & Customization Contract, Shared Infrastructure |

A naive `copier update` against a consumer whose `CLAUDE.md` has no sentinel boundaries produces heavy inline conflict markers across the whole file — which is exactly why the operators have been unable to produce clean PRs even in the few cases where the push would have succeeded.

### 2.4 Empty PR ≠ template parity (silent drift audit)

`copier update` short-circuits at the ref level: when the consumer's `_commit` matches the template's latest tag, it prints `Keeping template version vX.Y.Z` and exits with no file-level comparison. The `changed=false` that our workflow emits in that case is honest — **no diff was produced by this run** — but it is not the same as "all template-ownable content is currently in sync." Files silently drift in two ways:

1. **Files listed in `_skip_if_exists`** are never updated by `copier update`. Intentional for scaffolds (`README.md`, `CHANGELOG.md`, `LICENSE`, `.env.example`, the `tools.py` / `resources.py` / `prompts.py` / `domain.py` starters) — but also affects `scripts/bump_manifests.py` and `.gitignore`, which *are* drifting:
   - `markdown-vault-mcp/scripts/bump_manifests.py`: doctext references "three manifest paths" (plural, obsolete); missing `if not server_path.exists()` guard; different identifier bump logic.
   - `image-generation-mcp/scripts/bump_manifests.py`: has local defensive `isinstance()` checks that the template lacks; missing the newer "additional versioned manifests" doc paragraph.
   - `scholar-mcp/scripts/bump_manifests.py`: ✓ matches template.
   - All three `.gitignore` files: consistent small stylistic diff from template (missing section-header comments).
2. **Files *not* in `_skip_if_exists` that the consumers have modified anyway** — these WILL update on next template change, producing either a clean overwrite (if the consumer never needed the edit) or a conflict marker (if the consumer customized it):
   - `Dockerfile`: all three consumers diverge. `image-generation-mcp` genuinely needs its customization (`--extra all` for provider SDK extras, git-lfs installation, different COPY strategy).
   - `compose.yml`: `markdown-vault-mcp` diverges.
   - `docker-entrypoint.sh`: all three diverge.
   - `codecov.yml`: `image-generation-mcp` diverges by one line (`__main__.py` ignore).
   - `docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md`: all three diverge — these are template starters the domains extended.

Empirical canary: `image-generation-mcp` run `24791600780` dispatched `copier-update.yml`, copier exited with `Keeping template version 1.1.4`, `changed=false`, no branch push, no PR opened. The happy-path is now demonstrably working at the ref level — but the drift above will become visible (as conflict markers) the moment the template touches any of those files in a release.

### 2.5 What is NOT broken

- `pyproject.toml` sentinels (`PROJECT-DEPS-*`, `PROJECT-EXTRAS-*`) are correctly placed in all three consumers.
- `config.py` sentinels (`CONFIG-FIELDS-*`, `CONFIG-FROM-ENV-*`) are correctly placed in all three consumers.
- The template's own `copier-update.yml.jinja` logic (conflict counting, label creation, `--conflict=inline`, `force-with-lease` push, PR body assembly) is correct.
- `template-ci.yml` correctly gates the template with a full smoke render + idempotence check on Python 3.11–3.14.
- `fastmcp-pvl-core` is stable at v1.0.0-rc.1 and not implicated in either failure mode.

## 3. Design

### 3.1 Decision A — token strategy

**Short-term — DONE.** `RELEASE_TOKEN` has been re-issued with `workflow` scope and rotated across all four repos.

**Follow-ups (filed as issues, not part of this spec):**
- Migrate `copier-update.yml` to a GitHub App installation token via `actions/create-github-app-token`. Per-repo scoping, automatic rotation, no human-tied identity on automated commits. Dependabot/Renovate pattern.
- Sentinel-protect shared `docs/deployment/*.md` + `docs/guides/authentication.md`. Phase 1.5 converges these, which is the right near-term answer, but longer term each consumer may want to add deployment-specific caveats inline. Introduce `DOCS-DEPLOYMENT-EXTRA-*` / similar sentinel blocks analogous to `CONFIG-FIELDS-*`.

### 3.2 Decision B — CLAUDE.md migration order

Reject the naive path of "cut v1.1.5 first, let copier resolve everything." A `copier update` against an unsentineled `CLAUDE.md` would produce a wall of conflict markers requiring hand-resolution in every consumer — the same friction that has blocked the team to date.

Instead: **pre-migrate each consumer to the v1.1.4 sentinel shape in isolation, then bump the template.** Three small migration PRs now + one trivial follow-up PR per consumer after the v1.1.5 release.

### 3.3 Phased plan

**Phase 1 — unblock automation (mostly done)**
1. ~~Re-issue `RELEASE_TOKEN` with `workflow` scope.~~ **Done.**
2. File follow-up issue: "migrate copier-update workflow to GitHub App token" (Option B). Non-blocking.

**Phase 1.5 — drift triage (one pass, before Phase 2 work begins)**

For each drifted file identified in §2.4, decide: **converge** (force-sync consumer to template, discarding local edits) or **sentinel-protect** (add `DOCKERFILE-DEPS-*` / `COMPOSE-ENV-*` / etc. markers to the template's `.jinja`, then re-introduce the local edits inside the sentinel block). Default bias:

- `.gitignore`: converge. The stylistic drift is noise.
- `scripts/bump_manifests.py`: converge on scholar's (template-matching) shape. The other two's divergent versions are drift, not intentional customization — image-gen's defensive isinstance checks are the only bit worth upstreaming to the template first (small template PR).
- `docker-entrypoint.sh`: inspect diff; likely converge.
- `Dockerfile`: **sentinel-protect.** Image-gen's `--extra all` + git-lfs + COPY strategy are legitimate domain needs. Add `DOCKERFILE-APT-DEPS-*` + `DOCKERFILE-UV-EXTRAS-*` sentinel markers to `Dockerfile.jinja`.
- `compose.yml`: sentinel-protect if MV's divergence is domain-driven (volumes etc.); otherwise converge.
- `codecov.yml`: converge (image-gen's `__main__.py` ignore is a one-liner worth upstreaming into the template's codecov.yml.jinja).
- `docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md`: **converge** (keep template-owned). Future changes in `fastmcp-pvl-core` (auth flow, OIDC config, deployment patterns) will naturally want to propagate into these pages across the fleet; losing them to `_exclude` would orphan that channel. Domain additions should be appended as separate pages (the consumers already do this — each has its own `docs/guides/*.md` for domain-specific content). If any consumer genuinely needs to customize the core docs, that's a signal for a follow-up effort to introduce sentinel blocks inside these pages — track as a separate issue ("sentinel-protect shared docs/deployment + docs/guides pages"), not part of this spec.

Output of this phase: a small template PR adding any new sentinels + small consumer PRs converging the non-customized drift. This is the least glamorous phase but it means Phase 4's bot PRs will be *small* rather than *unmergeable*.

**Phase 2 — CLAUDE.md sentinel migration (three small PRs against template v1.1.4)**
3. `markdown-vault-mcp`: finish review on existing `refactor/claude-md-sentinels` branch, merge into main. The "drop Shared Infrastructure" commit on that branch is harmless — template v1.1.5 restores the section via the TEMPLATE-OWNED block on the next copier-update pass.
4. `scholar-mcp`: new migration PR that:
   - Wraps existing `## Project Structure` and `## Key Patterns` sections in `<!-- DOMAIN-START -->` / `<!-- DOMAIN-END -->` markers.
   - Adopts the v1.1.4 template-owned block verbatim (Conventions, Hard PR Gates, GitHub Review Types, Documentation Discipline, Logging Standard, Config & Customization Contract), enclosed in the `<!-- ===== TEMPLATE-OWNED SECTIONS BELOW ===== -->` / `<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->` fence.
   - Preserves domain content (async task queue, rate limiter patterns) inside DOMAIN blocks.
5. `image-generation-mcp`: same as scholar-mcp. Preserve provider-specific "Key Patterns" inside a DOMAIN block.

Each PR is a structural move of existing text — no new content, no deletions beyond "move into sentinel block". The existing gate (ruff / ruff format --check / mypy / pytest) runs unchanged; CLAUDE.md is not code, so the gate's role is regression-only.

**Phase 3 — release template v1.1.5**
6. Merge `feat/shared-infra-claude-md` into `fastmcp-server-template/main`.
7. Dispatch `template-release.yml` with `bump: patch` → tags `v1.1.5`, cuts GitHub release.

**Phase 4 — propagate + steady-state verification**
8. Manually dispatch `copier-update.yml` in each of the three consumers (don't wait for Monday cron). Expected diff per consumer: `.copier-answers.yml:_commit` bump + Shared Infrastructure insertion inside the TEMPLATE-OWNED block of CLAUDE.md. Review, verify CI green, merge. **These are the first operator-mergeable bot PRs the fleet will have seen.**
9. Wait for the next Monday cron. Expected outcome in each consumer: green no-op run, `Detect changes` → `changed=false`, no branch push, no PR. **This validates the "empty PR" success case the user flagged as never having worked.**
10. Add a template-ci assertion that rendered CLAUDE.md contains both `DOMAIN-START` and `TEMPLATE-OWNED SECTIONS BELOW` sentinel markers — cheap regression guard. New step in `template-ci.yml` after `pytest`:
    ```yaml
    - name: CLAUDE.md sentinel structure
      working-directory: /tmp/smoke
      run: |
        grep -q 'DOMAIN-START' CLAUDE.md || { echo "::error::missing DOMAIN-START"; exit 1; }
        grep -q 'TEMPLATE-OWNED SECTIONS BELOW' CLAUDE.md || { echo "::error::missing TEMPLATE-OWNED fence"; exit 1; }
        grep -q 'TEMPLATE-OWNED SECTIONS END' CLAUDE.md || { echo "::error::missing TEMPLATE-OWNED end fence"; exit 1; }
    ```

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
| Phase-4 bot PR surfaces a consumer rebase gap not caught here | Low-Medium (IG's mcp_server→server gap is fixed, but there could be others) | Bot PR arrives CI-red; operator has to hand-fix on top of the bot commit | Compare `copier copy` dry-render against main before dispatching Phase 4 (§6 step 4); if diff shows unexpected non-CLAUDE.md files, investigate before dispatching bot |

## 5. Success criteria

**All five criteria below are hard gates. An acceptance criterion is not just a checkbox — for each one, a human must inspect the artifact (PR diff, workflow run log) and confirm the intent matches the outcome.**

1. At least one consumer has a merged PR on `copier/update` branch produced by the `copier-update.yml` workflow (cron or `workflow_dispatch` — same code path) that required no hand-fixes on top of the bot commit. Kills the "never produced a mergeable PR" bug.
2. At least one consumer has a successful workflow run that exits with "no changes" and opens no PR. Kills the "never produced an empty PR" bug — the workflow intentionally doesn't open a PR when there's no diff, so a green no-op run *is* the "empty PR" success case. *Partial credit already in hand:* image-gen run `24791600780` demonstrated this at the ref level; still need the file-level confirmation that comes from Phase 1.5 + 4.
3. All three consumers have `CLAUDE.md` with both `DOMAIN-START`/`DOMAIN-END` and `TEMPLATE-OWNED` sentinel structure, matching the v1.1.5 template shape.
4. Template v1.1.5 is tagged and released.
5. `template-ci.yml` asserts the rendered CLAUDE.md structure so future drift is caught in the template's own PR gate.
6. The Phase 4 bot PR on each consumer was **reviewed by a human and approved on its diff**, not merged blindly on green CI. This is an explicit criterion because the two failure modes this spec addresses (unmergeable bot PR, false-empty PR) are not catchable by CI alone.

## 6. Test plan

- **Phase 1:** already validated — IG PR #192 proved the push path works end-to-end after rotation.
- **Phase 2:** for each consumer migration PR, run the existing gate locally (`uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest -x -q`). CLAUDE.md changes don't affect these, so the gate is regression-only.
- **Phase 3:** template-ci runs on the v1.1.5 merge PR (full smoke render + idempotence on Python 3.11–3.14).
- **Phase 4, pre-dispatch dry run:** for each consumer, before dispatching `copier-update.yml`, do a local dry-render against v1.1.5 in a scratch checkout to preview the diff:
  ```bash
  cd /tmp/ && git clone <consumer-repo> scratch-<consumer> && cd scratch-<consumer>
  uvx copier update --trust --defaults --skip-answered --conflict=inline --vcs-ref v1.1.5
  git status && git diff --stat
  ```
  If the diff contains anything outside CLAUDE.md + `.copier-answers.yml` + `.github/workflows/copier-update.yml`, investigate before dispatching the bot.
- **Phase 4, bot PR:** dispatch `copier-update.yml` per consumer. Inspect the bot-opened PR; green CI and sentinel-only CLAUDE.md diff = merge.
- **Phase 4, steady-state cron:** the first Monday cron after all three consumer PRs merge must produce green no-op runs. If any produces a non-empty diff, it indicates live template drift in that week — triage as a new spec, not a bug in this one.

## 7. Rollback

Each phase is independently revertable:
- Phase 1: PAT rotation already done; nothing to roll back for this spec.
- Phase 2: revert the per-consumer migration PR. CLAUDE.md has no runtime effect.
- Phase 3: `git revert` the v1.1.5 release commit and tag (or simply don't roll forward any consumer).
- Phase 4: revert the consumer copier-update PRs individually; remove the template-ci assertion if it proves too rigid.
