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

**Fallback (documented, not chosen):** if the Renovate `[dependency-groups]`
bug (below) proves blocking, revert to Dependabot downstream (pip only,
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
running `renovatebot/github-action`, authenticated with `RELEASE_TOKEN`
(`contents:write` + `pull_requests:write` already suffice; the `github-actions`
manager is disabled so no `workflows:write` is needed downstream).

**Delete — `.github/dependabot.yml.jinja`.** Renovate replaces it entirely.

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

- **Downstream:** reuse `RELEASE_TOKEN` — **no new secret**, no permission
  change (actions manager disabled ⇒ `contents:write` + `pull_requests:write`
  is enough). `README.md.jinja`'s GitHub-secrets table (currently three rows)
  stays as-is; optionally note Renovate reuses `RELEASE_TOKEN`.
- **Upstream (this repo):** the runner needs `workflows:write` in addition;
  extend `RELEASE_TOKEN`'s scope here.
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
- **Repo-setting prerequisites** (per repo, cannot be set by a rendered file):
  "Allow auto-merge" enabled **and** branch protection with required status
  checks. Without required checks, `automerge` merges immediately on open. The
  spec's rollout step must verify/enable these; consider having
  `bootstrap.yml(.jinja)` set them via the GitHub API as a follow-up so new
  scaffolds self-configure (future enhancement, not blocking).

## Validation strategy

- **`[dependency-groups]` smoke test (blocking gate before fleet rollout).**
  The fleet uses PEP 735 `[dependency-groups]` (`dev` group). Renovate has a
  known bug updating deps inside `[dependency-groups]`
  (renovatebot/renovate discussion #41716, "No depName found after updating").
  Before rolling to the fleet, run Renovate (dry-run or against one throwaway
  repo/render) and confirm it updates a `dev`-group dependency **and** the
  `uv.lock` cleanly. If it fails and no config workaround exists, take the
  Dependabot fallback for the downstream side.
- **Upstream `renovate.json` can't ride `template-ci.yml`.** The render gate
  produces a `/tmp` project; Renovate runs against a live GitHub repo. Validate
  Piece D with `renovate --dry-run` (a CI job or local run with `LOG_LEVEL=debug`)
  asserting the customManager *detects* the known pins, plus a manual review of
  the first real Renovate run on this repo.
- Known-narrow Renovate-uv bugs that **do not** apply here: custom PyPI index
  (#40201) — fleet uses none; Docker-sidecar quoting (#40660) — runner uses the
  default binary source, not `binarySource: docker`.

## Migration / rollout

1. **This template PR:** add upstream `renovate.json` + `renovate.yml`; add
   `renovate.json.jinja` + `renovate.yml.jinja`; delete `dependabot.yml.jinja`;
   update docs (README secrets note, CLAUDE.md/guides as needed). Render gate
   green.
2. Run the `[dependency-groups]` smoke test. Proceed only if it passes (else
   fallback).
3. **Template release** (`workflow_dispatch`, manual — never autonomous).
4. **Fleet convergence** via `copier update` per downstream repo (own PRs).
   Per-repo checklist: confirm "Allow auto-merge" + branch protection required
   checks; confirm `RELEASE_TOKEN` present; delete the now-removed
   `dependabot.yml`.
5. Watch the first downstream Renovate run; tune `packageRules`/schedule.

## Risks

- **`[dependency-groups]` bug** — mitigated by the blocking smoke test +
  documented Dependabot fallback.
- **Auto-merge without required checks** merges immediately — mitigated by the
  rollout prerequisite check.
- **Renovate noise** (onboarding PR, dependency dashboard) — tune `extends` /
  schedule; acceptable one-time cost.
- **Upstream token scope** — needs `workflows:write`; easy to add.

## Out of scope / future

- Template-side Python base-floor sweep (notch onto upstream `renovate.json`).
- `bootstrap`-time auto-enable of "Allow auto-merge" + branch protection.
- Dedicated `RENOVATE_TOKEN` bot identity for attribution.
- SHA-pinning Actions for supply-chain hardening.
