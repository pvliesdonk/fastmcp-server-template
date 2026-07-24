# Fleet dependency automation: switch to Renovate

**Date:** 2026-07-23
**Status:** Design — awaiting review
**Repo:** `fastmcp-server-template` (changes here fan out to the fleet via `copier update`)

## Problem

Downstream projects are drowning in dependency-update toil. Two distinct
pains, confirmed with the maintainer:

1. **`uv.lock` refreshes pile up and are merged by hand.** Nothing keeps the
   locked resolution current within the existing `pyproject.toml` floors, and
   the routine bumps that do arrive never auto-merge.
2. **Downstream Dependabot bumps GitHub Actions in template-owned files.**
   Example: `markdown-vault-mcp` PRs #895/#896 re-pin `astral-sh/setup-uv` and
   `python-semantic-release` in the rendered `ci.yml` / `release.yml`. Those
   workflow files are **template-owned** (`.yml.jinja`, not in
   `_skip_if_exists`, overwritten on every `copier update`), so each downstream
   Action bump (a) diverges the repo from the template's `@vN` pin and (b)
   produces a PR the next `copier update` clobbers. Every downstream repo does
   this independently against the *same* pins — N repos × M actions of pure
   churn.

### The underlying insight: dependency ownership is split

| Dependency type | Pinned in | Owner | Correct bump path |
|---|---|---|---|
| **GitHub Actions** | `.yml.jinja` at `@vN` (major float) | **Template** | Bump the major *here* → `copier update` fans it out. Minor/patch already float on `@vN` — nothing to do. |
| **Python floors** (`>=`) | `pyproject.toml(.jinja)` | Mixed (template base + domain) | Template for base deps; downstream for domain deps. |
| **Locked versions** | `uv.lock` | **Downstream** (per-project resolution) | Refresh within floors, per repo. |

Each side should run dependency automation **only for what it owns**. Today
downstream Dependabot violates this by managing Actions it does not own.

### Why Dependabot can't fix the upstream side

Dependabot only scans real workflow filenames (`.github/workflows/*.yml|yaml`).
It **cannot read `.yml.jinja`**, so the template's Action pins — the single
source of truth for the whole fleet — are unmanageable by Dependabot. The
upstream side needs a scanner that can match arbitrary files.

## Goals

- Proactive `uv.lock` refresh downstream → PR → auto-merge on green.
- Auto-merge routine dependency PRs (patch + minor); majors stay human.
- Stop downstream from managing GitHub Actions; move Action-version truth
  upstream to the template, propagated by template release + `copier update`.
- Do it with **one** tool, not Dependabot and Renovate side-by-side, and with
  the **least** bespoke workflow code to own long-term.
- **Self-configure the repo prerequisites** for safe auto-merge ("Allow
  auto-merge" + branch protection requiring CI) from `bootstrap`, so a new
  scaffold needs no manual GitHub-settings clicks.

## Non-goals

- Auto-merging **major** bumps (breaking; human review always).
- A template-side **Python base-floor** sweep. Lock refresh + downstream floor
  management cover the felt pain; base floors move rarely. Future enhancement
  (notch onto the upstream Renovate config later).
- Changing the `@vN` (major-float) Action pin strategy or moving to SHA pins.

## Decision: complete switch to Renovate

Chosen over "Dependabot downstream / Renovate upstream" for two reasons:

1. **Single tool.** The split still puts two tools in the fleet — two mental
   models, two config dialects. The maintainer explicitly does not want that.
2. **Renovate *deletes* bespoke machinery instead of adding it.** Under
   Renovate the custom pieces become configuration, not hand-written workflows:

   | Piece | Custom-workflow design | Renovate-native |
   |---|---|---|
   | A. Proactive `uv lock --upgrade` → PR | new scheduled workflow | **`lockFileMaintenance`** |
   | B. Auto-merge patch/minor | new `dependabot/fetch-metadata` workflow | `packageRules` + `automerge` |
   | C. Actions owned upstream | edit `dependabot.yml` | disable `github-actions` manager downstream |
   | D. Scan `.jinja` for Action majors | grep + GH API + PR action | **`customManagers`** (regex) |

   The whole four-piece design collapses to **two `renovate.json` files** plus
   **two thin runner workflows** — and *zero* custom lock-refresh / auto-merge
   code to maintain. Smaller surface than even the original "run `uv sync` and
   PR" idea.

**Fallback (documented, not expected):** the `[dependency-groups]` blocker that
motivated this fallback is **already fixed** in Renovate `43.59.0` (see
Validation), so the fallback is now a deep contingency only. If Renovate's uv
support regresses in some future way, revert to Dependabot downstream (pip only,
`github-actions` ecosystem dropped) + custom lock-refresh and auto-merge
workflows, with Renovate only upstream for Piece D.

## Ops model: self-hosted runner, rendered by the template

The account is **personal, not an organization**. For a copier fleet the
self-hosted runner beats the Mend-hosted Renovate App:

- The hosted App must be **installed and granted per repo out-of-band** — a
  manual step the template cannot perform, fighting fleet convergence (every
  new scaffold would need a manual App grant).
- A **self-hosted runner** (`renovate.yml(.jinja)` running
  `renovatebot/github-action` on a schedule) is **rendered into every project**.
  Scaffold or `copier update` → the repo self-configures. No third-party app in
  the code, and it reuses tokens the fleet already provisions.

## Architecture

### Downstream (rendered by the template)

**New — `renovate.json.jinja`** (illustrative; exact keys verified against
Renovate docs at implementation):

```jsonc
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended", ":dependencyDashboard"],
  "enabledManagers": ["pep621"],            // uv/PEP 621; NOT github-actions (Piece C)
  "lockFileMaintenance": {                   // Piece A
    "enabled": true,
    "schedule": ["before 6am on monday"],
    "automerge": true
  },
  "packageRules": [
    {                                        // Piece B: patch+minor self-merge
      "matchUpdateTypes": ["patch", "minor"],
      "automerge": true
    },
    {                                        // majors stay human
      "matchUpdateTypes": ["major"],
      "automerge": false
    }
  ]
}
```

**New — `renovate.yml.jinja`** — scheduled workflow + `workflow_dispatch`
running `renovatebot/github-action`, authenticated with `RELEASE_TOKEN`.
Pin the runner's `renovate-version` input to a floor **`>= 43.59.0`** (the
release that fixes the `[dependency-groups]` bug — see Validation). Token scope:
`contents:write` + `pull_requests:write` suffice for Renovate itself (actions
manager disabled ⇒ no `workflows:write` needed for the *Renovate* run
downstream); the separate bootstrap job needs more (see Auto-merge safety).

**Edit — `bootstrap.yml.jinja`** — see the Auto-merge safety section: retarget
its `paths:` trigger from `.github/dependabot.yml` to `.github/renovate.json`,
keep seeding the `dependencies` label (Renovate applies it too), and add a job
that self-configures "Allow auto-merge" + branch protection.

**Delete — `.github/dependabot.yml.jinja`.** Renovate replaces it entirely.

**New — `ci.yml.jinja` aggregate gate job.** Add a single `ci-success` job
(`name: CI Success`) with `needs: [lint, typecheck, test, audit, secrets, vale,
structure]` and `if: {% raw %}${{ always() }}{% endraw %}` that fails if any
needed job's result is `failure`/`cancelled` (treating `skipped` as pass). This
gives branch protection **one drift-proof required context** to gate auto-merge
on, instead of enumerating seven check names that break whenever a job is
renamed or a path-filtered job is skipped. This is a deliberate scope addition
in service of item 3 (safe auto-merge).

### Upstream (this template repo)

**New — `renovate.json`** (real file, not rendered):

- `customManagers` (regex) matching `uses: <owner>/<repo>(/<subpath>)?@vN` in
  `**/*.jinja` (and any other non-standard files), datasource `github-tags` /
  `github-releases`, so Action **majors** in the jinja workflows are detected —
  **Piece D**. Must handle subpath actions (`github/codeql-action/analyze@v4`
  and `.../init@v4` → one upstream repo `github/codeql-action`; dedup so one PR,
  not two).
- Native `github-actions` manager for the template's **own real** workflows
  (`template-ci.yml`, `template-release.yml`, `claude*.yml`,
  `claude-code-review.yml`) — currently unmanaged; cleaned up as a bonus.
- Native `pep621` for the template's own `pyproject.toml`/dev tooling.
- Action **majors → PR only, never auto-merge** (breaking, human review).

**New — `.github/workflows/renovate.yml`** — real scheduled runner for this
repo. Needs a token with `contents:write` + `pull_requests:write` +
**`workflows:write`** (it edits workflow files). Reuse the `RELEASE_TOKEN`
pattern; extend its scope to include `workflows:write` on this repo (the
maintainer confirmed permissions are easy to add).

### Action pin inventory (Piece D scan target)

Current `@vN` pins across `.jinja` workflows the customManager must cover:

```
actions/attest-build-provenance@v4   actions/attest-sbom@v4
actions/cache@v6                     actions/checkout@v7
actions/download-artifact@v8         actions/github-script@v9
actions/upload-artifact@v7           anthropics/claude-code-action@v1
astral-sh/setup-uv@v8                codecov/codecov-action@v7
docker/build-push-action@v7          docker/login-action@v4
docker/metadata-action@v6            docker/setup-buildx-action@v4
docker/setup-qemu-action@v4          github/codeql-action/analyze@v4  (subpath)
github/codeql-action/init@v4  (subpath)
peter-evans/create-pull-request@v8
python-semantic-release/publish-action@v1
python-semantic-release/python-semantic-release@v1
vale-cli/vale-action@8
```

## Tokens & secrets

- **Downstream:** reuse `RELEASE_TOKEN` — **no new secret**. Renovate itself
  needs only `contents:write` + `pull_requests:write` (already granted). The
  bootstrap self-config job (item 3) additionally needs **`administration:write`**
  to set repo settings + branch protection — so `RELEASE_TOKEN`'s scope gains
  `administration:write` fleet-wide (maintainer confirmed permissions are easy
  to add). `README.md.jinja`'s GitHub-secrets table gains a note that
  `RELEASE_TOKEN` now also powers Renovate + bootstrap and lists the added
  scope; row count stays at three.
- **Upstream (this repo):** the Renovate runner needs `workflows:write` in
  addition (it edits workflow files); extend `RELEASE_TOKEN`'s scope here too.
- **Rejected alternative:** a dedicated `RENOVATE_TOKEN` per repo. Cleaner for
  attribution/least-privilege, but adds a secret to every existing downstream
  repo and to the scaffold token list (release_token / codecov / pypi / claude)
  for no functional gain — `copier-update.yml` already opens PRs under
  `RELEASE_TOKEN`, so Renovate doing the same is consistent. Revisit only if
  bot-identity attribution becomes desirable.

## Auto-merge safety

- Scope: **patch + minor only** (includes every `lockFileMaintenance` PR, which
  is within-floor by construction). Majors never auto-merge, either tool.
- `chore(deps):` commit type ⇒ **PSR cuts no release**, so auto-merges to `main`
  never trigger a surprise version bump downstream.
- **Repo-setting prerequisites, now self-configured by `bootstrap.yml.jinja`
  (item 3, in scope):** GitHub auto-merge requires "Allow auto-merge" enabled
  **and** branch protection with ≥1 required status check — without a required
  check, `automerge` merges immediately on open (defeating the gate). A rendered
  file cannot set these (they're repo settings, not repo contents), so bootstrap
  does it via the API on push-to-`main` + `workflow_dispatch`, idempotently:
  - `gh api -X PATCH /repos/{% raw %}${{ github.repository }}{% endraw %}
    -F allow_auto_merge=true`
  - `gh api -X PUT /repos/.../branches/main/protection` requiring the single
    **`CI Success`** context (the aggregate gate job), with
    `required_status_checks.strict=true` (PR must be up to date),
    **no** required approving reviews (a solo account has no second reviewer;
    requiring reviews would deadlock patch/minor auto-merge), and
    `enforce_admins=false` (so the owner can still push hotfixes).
  - Auth: the elevated `RELEASE_TOKEN` (`administration:write`), **not**
    `github.token` — `GITHUB_TOKEN` cannot change settings or branch protection.
  - The branch-protection context string is anchored to the gate job's exact
    `name:` (`CI Success`); if that job is renamed, bootstrap's required-check
    name must change in lockstep. Called out so the two never drift.
- **Renovate side of the gate:** `renovate.json` sets `automerge: true` only for
  `matchUpdateTypes: [patch, minor]` (and `lockFileMaintenance`); it relies on
  the branch protection above to hold the merge until `CI Success` is green.

## Validation strategy

### The `[dependency-groups]` bug — already fixed (no longer a blocking gate)

The fleet uses PEP 735 `[dependency-groups]` (a `dev` group). Renovate had a bug
updating deps inside `[dependency-groups]` under uv (discussion #41716, "No
depName found after updating" — Renovate ran `uv lock --upgrade-package`, then
failed post-update verification with `depName: undefined`). **Full detail for
the record:**

- **Introduced-visible in:** Renovate `43.58.0` (the version the reporter hit).
- **Root cause:** post-update verification assumed every extracted dep carries a
  `depName`; for a `[dependency-groups]` entry only `packageName` is present, so
  the lookup returned `undefined` and aborted the commit. (It only bit when
  Renovate actually committed — repos where the same update sat behind
  `minimumReleaseAge` never reached the failing step.)
- **Fix:** PR **#41720** (merged 2026-03-06) — falls back to `packageName` when
  `depName` is absent.
- **Released in:** Renovate **`43.59.0`** (2026-03-06).
- **The "workaround" is therefore just a version floor.** Pin the runner's
  `renovate-version >= 43.59.0`. Since 43.59.0 shipped four months before this
  design, any current `renovatebot/github-action` already bundles a Renovate far
  past it; the explicit floor is belt-and-suspenders against someone pinning an
  old action.
- **PEP 735 support itself is mature** — `[dependency-groups]` handling landed in
  PR #32148 well before this; #41716 was a narrow regression, not missing
  support.

The former "blocking smoke test" is downgraded to a **confirmation**: on the
first downstream Renovate run, verify one `dev`-group dependency updates and
`uv.lock` regenerates cleanly. If (unexpectedly) it regresses, the documented
Dependabot fallback still stands.

### Adjacent Renovate-uv bugs — verified NOT applicable

- **#41719** (uv.lock `lockedVersion` contaminates unrelated `pyproject.toml`,
  causing downgrades) — **requires multiple `pyproject.toml` files** in one
  repo (monorepo/workspace with `rangeStrategy: update-lockfile`). Every fleet
  repo is **single-pyproject**, so this cannot trigger. (Corollary: do not adopt
  a multi-package layout without revisiting this.)
- **#40201** (lockFileMaintenance uses wrong index) — fleet uses **no** custom
  PyPI index.
- **#40660** (bash not quoted running `uv lock` in Docker sidecar) — runner uses
  the **default** binary source, not `binarySource: docker`.

### Upstream `renovate.json` can't ride `template-ci.yml`

The render gate produces a `/tmp` project; Renovate runs against a live GitHub
repo. Validate Piece D with `renovate --dry-run` (a CI job or local run with
`LOG_LEVEL=debug`) asserting the `customManagers` regex *detects* the known
`@vN` pins (including the two `codeql-action` subpaths dedup to one), plus a
manual review of the first real Renovate run on this repo.

## Migration / rollout

1. **Prep the `RELEASE_TOKEN` scope** on every fleet repo + this one:
   add `administration:write` (all repos, for bootstrap) and `workflows:write`
   (this repo, for the upstream runner). One-time, out-of-band.
2. **This template PR:** add upstream `renovate.json` + `renovate.yml`; add
   `renovate.json.jinja` + `renovate.yml.jinja` (pin `renovate-version >=
   43.59.0`); add the `CI Success` aggregate gate job to `ci.yml.jinja`; edit
   `bootstrap.yml.jinja` (retarget `paths:`, add the auto-merge + branch-
   protection self-config job); delete `dependabot.yml.jinja`; update docs
   (README secrets note, CLAUDE.md/guides as needed). Render gate green +
   upstream `renovate --dry-run` detects the pins.
3. **Template release** (`workflow_dispatch`, manual — never autonomous).
4. **Fleet convergence** via `copier update` per downstream repo (own PRs).
   Per-repo: `copier update` renders the new workflows + gate job and removes
   `dependabot.yml`; the first push to `main` runs bootstrap, which enables
   auto-merge + branch protection automatically. Confirm `RELEASE_TOKEN` scope
   was updated (step 1) before relying on auto-merge.
5. **Confirm** on the first downstream Renovate run: a `dev`-group dep updates +
   `uv.lock` regenerates cleanly; a patch/minor PR auto-merges once `CI Success`
   is green; a major PR stays open. Tune `packageRules`/schedule.

## Risks

- **`[dependency-groups]` bug** — **already fixed** in `43.59.0`; mitigated by
  the `renovate-version` floor. Dependabot fallback documented but not expected.
- **Auto-merge with no required check merges immediately** — mitigated because
  bootstrap installs branch protection requiring `CI Success` before any
  Renovate PR can merge. If bootstrap hasn't run yet (or `RELEASE_TOKEN` lacks
  `administration:write`), branch protection is absent → auto-merge would fire
  early; step 1 + the bootstrap-before-first-PR ordering guard against it.
- **Gate-job ↔ required-check name drift** — the branch-protection context is
  the literal string `CI Success`; renaming the job without updating bootstrap
  silently disables the gate. Kept in one place, called out in both files.
- **`enforce_admins=false`** means the owner can push directly to `main` — this
  is intentional (hotfix path) but means protection is not absolute.
- **Renovate noise** (onboarding PR, dependency dashboard) — tune `extends` /
  schedule; acceptable one-time cost.
- **Token scope creep** — `RELEASE_TOKEN` now spans release + copier-update +
  Renovate + repo-administration. Broader blast radius if leaked; accepted in
  favour of not proliferating secrets (see Tokens § rejected alternative).

## Out of scope / future

- Template-side Python base-floor sweep (notch onto upstream `renovate.json`).
- Dedicated `RENOVATE_TOKEN` bot identity for attribution.
- SHA-pinning Actions for supply-chain hardening.

_(Note: `bootstrap`-time auto-enable of "Allow auto-merge" + branch protection
was moved **into** scope — see Auto-merge safety.)_
