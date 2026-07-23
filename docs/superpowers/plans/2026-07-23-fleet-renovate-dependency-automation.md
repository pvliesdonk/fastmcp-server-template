# Fleet Dependency Automation (Renovate switch) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Dependabot fleet-wide with Renovate: downstream projects get proactive `uv.lock` maintenance + patch/minor auto-merge; the template repo gets a Renovate detector that catches GitHub Action *major* bumps in the Jinja-templated workflows Dependabot cannot read; bootstrap self-configures the repo settings that make auto-merge safe.

**Architecture:** Dependency ownership is split — Actions are template-owned (`.yml.jinja`, propagated by `copier update`), `uv.lock` is downstream-owned. Each side runs Renovate only for what it owns. Downstream Renovate (`renovate.json.jinja` + a rendered runner) manages only `uv.lock` (`rangeStrategy: update-lockfile`, `lockFileMaintenance`), never Action pins. The template's own Renovate (`.github/renovate.json` + a template-only runner) uses a `customManagers` regex to bump Action majors in `**/.github/workflows/*.jinja`. A new drift-proof `CI Success` aggregate job gives branch protection one required context; `bootstrap.yml.jinja` enables "Allow auto-merge" + branch protection via the GitHub API.

**Tech Stack:** Copier (Jinja2 templates), Renovate (`renovatebot/github-action@v46`, Renovate CLI ≥ 43.59.0), GitHub Actions, `uv`, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-07-23-fleet-renovate-dependency-automation-design.md`

## Global Constraints

- **Renovate CLI floor: `>= 43.59.0`** (fixes the `[dependency-groups]` `depName` bug, PR #41720). Satisfied by `renovatebot/github-action@v46`'s bundled default; do not pin an older `renovate-version`.
- **Auto-merge scope: patch + minor only.** Majors never auto-merge (either side). Upstream (template) never auto-merges anything.
- **Do NOT change existing Action pin styles.** `astral-sh/setup-uv@v8.2.0` and `python-semantic-release/*@v10.5.3` stay exact-pinned; `@vN` pins stay major-float. The detector handles both.
- **Token: reuse `RELEASE_TOKEN`** everywhere (no new secret). Never use `github.token`/`GITHUB_TOKEN` for the Renovate run or the bootstrap settings calls — a PR opened by `GITHUB_TOKEN` does not re-trigger CI, and it cannot change repo settings.
- **Jinja workflow files must wrap GitHub Actions expressions:** every `${{ … }}` inside a `*.jinja` file goes inside `{% raw %}…{% endraw %}` (copier interprets `{{ }}`). Real `.yml` files (template-only) do not.
- **Copier reads from the git index.** To render with `--vcs-ref=HEAD` you must `git commit` first; uncommitted edits are invisible to the render gate.
- **Branch-protection required context is the literal string `CI Success`.** If the aggregate job's `name:` ever changes, `bootstrap.yml.jinja` must change in lockstep.

---

## Prerequisites (manual, out-of-band — do before relying on the automation)

These are documented here and in the spec; they are **not** code steps but the automation is inert without them. Do NOT block plan implementation on them, but note them in the PR body.

1. **Extend `RELEASE_TOKEN` scope** to `contents:write` + `pull_requests:write` + `administration:write` on every fleet repo (bootstrap needs `administration:write`), and additionally `workflows:write` on the **template repo** (its runner edits workflow files).
2. **Add a `RELEASE_TOKEN` secret to the template repo itself** if absent (its `template-*` workflows currently use none) — `gh secret set RELEASE_TOKEN`.

---

## Task 1: Upstream detector (template repo's own Renovate)

Adds the template's Renovate config + a template-only runner, and excludes both from rendering. Includes an **offline regex self-test** proving the `customManagers` pattern extracts the right `depName`/`currentValue` (subpaths stripped, `codeql-action` deduped). The live `renovate --dry-run` is a post-deploy confirmation, not a local step.

**Files:**
- Create: `.github/renovate.json`
- Create: `.github/workflows/template-renovate.yml`
- Modify: `copier.yml` (add two `_exclude` entries)
- Test: `scripts/tests/test_renovate_custom_manager.py`

**Interfaces:**
- Produces: `.github/renovate.json` with a `customManagers[0].matchStrings[0]` regex the test reads back; `managerFilePatterns` targeting `.github/workflows/*.jinja`.

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/test_renovate_custom_manager.py`:

```python
"""Offline self-test for the upstream customManagers regex in .github/renovate.json.

Reads the actual matchString from the committed config and applies it to every
Jinja workflow, asserting the capture groups behave: depName is always
owner/repo (subpath stripped), codeql-action dedupes to one depName, and known
pins are captured with the right currentValue. Keeps the regex and its
contract in sync — edit the regex, this test re-verifies it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / ".github" / "renovate.json"
WORKFLOW_DIR = REPO / ".github" / "workflows"


def _matcher() -> re.Pattern[str]:
    cfg = json.loads(CONFIG.read_text())
    (manager,) = cfg["customManagers"]
    (match_string,) = manager["matchStrings"]
    # Renovate uses JS/RE2 named groups `(?<name>)`; Python `re` needs `(?P<name>)`.
    return re.compile(match_string.replace("(?<", "(?P<"))


def _captures() -> list[tuple[str, str]]:
    pat = _matcher()
    hits: list[tuple[str, str]] = []
    for wf in WORKFLOW_DIR.glob("*.jinja"):
        for m in pat.finditer(wf.read_text()):
            hits.append((m.group("depName"), m.group("currentValue")))
    return hits


def test_every_depname_is_owner_slash_repo() -> None:
    # Exactly one slash proves the action subpath (e.g. codeql-action/init) is stripped.
    for dep_name, _ in _captures():
        assert dep_name.count("/") == 1, f"subpath not stripped: {dep_name!r}"


def test_codeql_action_dedupes_to_repo() -> None:
    dep_names = {d for d, _ in _captures()}
    assert "github/codeql-action" in dep_names
    assert not any(d.startswith("github/codeql-action/") for d in dep_names)


def test_known_pins_captured() -> None:
    pairs = set(_captures())
    assert ("astral-sh/setup-uv", "v8.2.0") in pairs  # exact pin captured whole
    assert ("actions/checkout", "v7") in pairs  # major-float pin captured
    assert len({d for d, _ in pairs}) >= 15  # sanity: most actions found
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --no-project --with pytest -- pytest scripts/tests/test_renovate_custom_manager.py -q`
Expected: FAIL — `.github/renovate.json` does not exist yet (`FileNotFoundError`).

- [ ] **Step 3: Create `.github/renovate.json`**

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended", ":dependencyDashboard"],
  "labels": ["dependencies"],
  "customManagers": [
    {
      "customType": "regex",
      "description": "Bump GitHub Action pins inside Jinja-templated workflow files. Dependabot and Renovate's native github-actions manager cannot read *.jinja, so the template's Action pins — the single source of truth for the whole fleet — are invisible to them. This scans them; downstream inherits bumps via template release + copier update.",
      "managerFilePatterns": ["/^\\.github/workflows/.*\\.jinja$/"],
      "matchStrings": [
        "uses:\\s+(?<depName>[\\w.-]+/[\\w.-]+)(?:/[\\w./-]+)?@(?<currentValue>v?\\d[^\\s\"']*)"
      ],
      "datasourceTemplate": "github-tags",
      "versioningTemplate": "docker"
    }
  ],
  "packageRules": [
    {
      "description": "The template NEVER auto-merges: Action majors are breaking and downstream inherits them via a reviewed template release. Native github-actions manager covers the template's own real workflows.",
      "matchManagers": ["github-actions", "custom.regex"],
      "automerge": false
    }
  ]
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --no-project --with pytest -- pytest scripts/tests/test_renovate_custom_manager.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Validate the config with Renovate's own validator**

Run: `npx --yes --package renovate -- renovate-config-validator .github/renovate.json`
Expected: `Config validated successfully` (no errors). If it reports the `custom.regex` manager id, that confirms the customManager is recognized.

- [ ] **Step 6: Create the template-only runner `.github/workflows/template-renovate.yml`**

This is a real `.yml` (template-repo only), so **no `{% raw %}`**:

```yaml
name: Renovate (template)

# Self-hosted Renovate for THIS template repo. Scans the real workflows via the
# native github-actions manager AND the Jinja-templated workflows via the
# custom.regex manager in .github/renovate.json — catching GitHub Action MAJOR
# updates that Dependabot cannot see (Dependabot can't parse *.jinja). Opens PRs
# for human review; never auto-merges. Downstream inherits Action bumps through
# a template release + copier update, not through per-repo Dependabot.

on:
  schedule:
    - cron: "0 6 * * 1" # Monday 06:00 UTC
  workflow_dispatch:

permissions:
  contents: read

jobs:
  renovate:
    name: Renovate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - name: Run Renovate
        uses: renovatebot/github-action@v46
        with:
          configurationFile: .github/renovate.json
          token: ${{ secrets.RELEASE_TOKEN }}
        env:
          RENOVATE_REPOSITORIES: ${{ github.repository }}
```

- [ ] **Step 7: Exclude both upstream files from rendering**

In `copier.yml`, in the `_exclude:` list, after the `template-release.yml` line (currently `copier.yml:125`), add:

```yaml
  - ".github/renovate.json"                    # upstream detector config — template-repo only
  - ".github/workflows/template-renovate.yml"  # upstream Renovate runner — template-repo only
```

These have no `.jinja` twins and distinct paths, so excluding them cannot affect the downstream `renovate.json` / `renovate.yml` rendered from the `.jinja` files added in Task 2.

- [ ] **Step 8: Lint the new workflow**

Run: `actionlint .github/workflows/template-renovate.yml` (or, if `actionlint` is unavailable: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/template-renovate.yml'))"`)
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add .github/renovate.json .github/workflows/template-renovate.yml \
        copier.yml scripts/tests/test_renovate_custom_manager.py
git commit -m "feat(deps): add upstream Renovate detector for Action majors in jinja workflows"
```

---

## Task 2: Downstream Renovate config + runner; remove Dependabot

Adds the rendered downstream Renovate config and runner, and deletes the Dependabot config. Downstream Renovate manages **only** `uv.lock` — `rangeStrategy: update-lockfile` means it never edits `pyproject.toml` floors (which would be clobbered by `copier update` for template-owned base deps).

**Files:**
- Create: `renovate.json.jinja`
- Create: `.github/workflows/renovate.yml.jinja`
- Delete: `.github/dependabot.yml.jinja`

**Interfaces:**
- Consumes: `RELEASE_TOKEN` secret (downstream).
- Produces (after render): `renovate.json` at repo root, `.github/workflows/renovate.yml`.

- [ ] **Step 1: Create `renovate.json.jinja`**

Static JSON (no template variables — copier renders it verbatim):

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended", ":dependencyDashboard"],
  "labels": ["dependencies"],
  "enabledManagers": ["pep621"],
  "rangeStrategy": "update-lockfile",
  "lockFileMaintenance": {
    "enabled": true,
    "schedule": ["before 6am on monday"],
    "automerge": true
  },
  "packageRules": [
    {
      "description": "Routine bumps self-merge once CI is green; majors wait for a human.",
      "matchUpdateTypes": ["patch", "minor"],
      "automerge": true
    },
    {
      "matchUpdateTypes": ["major"],
      "automerge": false
    }
  ]
}
```

Notes for the reviewer: `enabledManagers: ["pep621"]` intentionally omits `github-actions` (Piece C — Actions are template-owned). `rangeStrategy: "update-lockfile"` keeps Renovate inside existing `pyproject.toml` floors (lock-only movement). `lockFileMaintenance` runs `uv lock --upgrade` weekly and auto-merges the batched refresh.

- [ ] **Step 2: Validate the config**

Run: `npx --yes --package renovate -- renovate-config-validator renovate.json.jinja`
Expected: `Config validated successfully` (the file is valid JSON with no jinja tags, so the validator reads it directly).

- [ ] **Step 3: Create `.github/workflows/renovate.yml.jinja`**

This is a `.jinja` file, so **wrap every `${{ … }}` in `{% raw %}…{% endraw %}`**:

```yaml
name: Renovate

# Self-hosted Renovate for this project. Keeps uv.lock current within the
# pyproject.toml floors (lockFileMaintenance) and auto-merges patch/minor
# updates once CI is green. GitHub Actions are intentionally NOT managed here —
# their pins live in the copier template and arrive via `copier update`.

on:
  schedule:
    - cron: "0 6 * * 1" # Monday 06:00 UTC
  workflow_dispatch:

permissions:
  contents: read

jobs:
  renovate:
    name: Renovate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - name: Run Renovate
        uses: renovatebot/github-action@v46
        with:
          configurationFile: renovate.json
          token: {% raw %}${{ secrets.RELEASE_TOKEN }}{% endraw %}
        env:
          RENOVATE_REPOSITORIES: {% raw %}${{ github.repository }}{% endraw %}
```

- [ ] **Step 4: Delete the Dependabot config**

Run: `git rm .github/dependabot.yml.jinja`
Expected: file staged for deletion.

- [ ] **Step 5: Verify Dependabot is fully gone from the template**

Run: `git ls-files | grep -i dependabot`
Expected: **no output** (empty). If any file remains, it is a stray reference — handle it in Task 5's class-sweep.

- [ ] **Step 6: Commit**

```bash
git add renovate.json.jinja .github/workflows/renovate.yml.jinja
git commit -m "feat(deps): render Renovate downstream (uv.lock maintenance + auto-merge), drop Dependabot"
```

---

## Task 3: `CI Success` aggregate gate job

Adds one drift-proof aggregate job to the rendered CI so branch protection has a single required context to gate auto-merge on. The `needs:` list conditionally includes `structure` (the only jinja-guarded job).

**Files:**
- Modify: `.github/workflows/ci.yml.jinja` (append a job at end of file, after `ci.yml.jinja:397`)

**Interfaces:**
- Consumes: existing job ids `lint, typecheck, test, audit, secrets, vale` (always present) and `structure` (present iff `enable_structural_gate`).
- Produces: a job named exactly `CI Success` — the required-check context bootstrap (Task 4) installs.

- [ ] **Step 1: Append the aggregate job to `ci.yml.jinja`**

At the very end of the file (after the `{% endif %}` on line 397), add:

```yaml

  ci-success:
    name: CI Success
    # Single aggregate gate for branch protection / Renovate auto-merge to
    # require. Succeeds only if every upstream job succeeded or was skipped;
    # fails if any failed or was cancelled. Requiring this ONE context is
    # drift-proof — renaming an individual job never silently disables the gate.
    needs:
      - lint
      - typecheck
      - test
      - audit
      - secrets
      - vale
{% if enable_structural_gate %}
      - structure
{% endif %}
    if: {% raw %}${{ always() }}{% endraw %}
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Verify all required jobs passed
        env:
          RESULTS: {% raw %}${{ join(needs.*.result, ' ') }}{% endraw %}
        run: |
          echo "Upstream job results: $RESULTS"
          for result in $RESULTS; do
            if [ "$result" != "success" ] && [ "$result" != "skipped" ]; then
              echo "::error::A required job did not pass (result: $result)"
              exit 1
            fi
          done
          echo "All required jobs passed."
```

- [ ] **Step 2: Commit (render-verified in Task 6)**

The aggregate references jinja-guarded `structure`; correctness under both `enable_structural_gate` values is verified by the full render gate in Task 6. Commit now:

```bash
git add .github/workflows/ci.yml.jinja
git commit -m "feat(ci): add CI Success aggregate gate job for branch protection"
```

---

## Task 4: Bootstrap self-configures auto-merge + branch protection

Extends `bootstrap.yml.jinja` to enable "Allow auto-merge" and install branch protection requiring the `CI Success` context — the repo settings a rendered file cannot set. Uses the elevated `RELEASE_TOKEN`.

**Files:**
- Modify: `.github/workflows/bootstrap.yml.jinja` (whole file — retarget trigger paths, add a job)

**Interfaces:**
- Consumes: `RELEASE_TOKEN` (needs `administration:write`); the `CI Success` context name from Task 3.

- [ ] **Step 1: Replace the whole `bootstrap.yml.jinja`**

Overwrite the file with:

```yaml
name: Bootstrap repo

# Seeds repository state that checked-in config references but GitHub does not
# create on its own:
#   1. The `dependencies` label Renovate applies to its PRs (GitHub silently
#      drops labels that don't exist).
#   2. Repository settings that make Renovate auto-merge SAFE — "Allow
#      auto-merge" plus branch protection requiring the `CI Success` check.
#      Without a required check, enabling auto-merge on a PR merges it
#      immediately; the gate is what holds the merge until CI is green.
#
# Idempotent: label create is `--force`; the settings/branch-protection calls
# are PATCH/PUT that converge to the same state on every run. The first push to
# the default branch applies everything; `workflow_dispatch` re-applies on demand.
#
# Auth: the settings + branch-protection calls need `administration:write`,
# which the default GITHUB_TOKEN lacks — they use RELEASE_TOKEN.

on:
  push:
    branches: [main]
    paths:
      - .github/workflows/bootstrap.yml
      - .github/renovate.json
      - renovate.json
  workflow_dispatch:

permissions:
  issues: write

jobs:
  labels:
    name: Ensure repository labels
    runs-on: ubuntu-latest
    steps:
      - name: Create dependencies label
        env:
          GH_TOKEN: {% raw %}${{ github.token }}{% endraw %}
          GH_REPO: {% raw %}${{ github.repository }}{% endraw %}
        run: |
          gh label create dependencies \
            --color 0366d6 \
            --description "Pull requests that update a dependency" \
            --force

  settings:
    name: Enable auto-merge + branch protection
    runs-on: ubuntu-latest
    steps:
      - name: Allow auto-merge and require CI Success on main
        env:
          GH_TOKEN: {% raw %}${{ secrets.RELEASE_TOKEN }}{% endraw %}
          REPO: {% raw %}${{ github.repository }}{% endraw %}
        run: |
          # Enable repository-level auto-merge.
          gh api -X PATCH "repos/${REPO}" -F allow_auto_merge=true

          # Require the single drift-proof CI Success context. No required
          # reviews (a solo account has no second reviewer — requiring one would
          # deadlock patch/minor auto-merge). enforce_admins=false keeps a
          # direct-push hotfix path for the owner.
          gh api -X PUT "repos/${REPO}/branches/main/protection" \
            --input - <<'JSON'
          {
            "required_status_checks": {
              "strict": true,
              "contexts": ["CI Success"]
            },
            "enforce_admins": false,
            "required_pull_request_reviews": null,
            "restrictions": null
          }
          JSON
```

- [ ] **Step 2: Lint the rendered-intent (yaml parse of the jinja skeleton)**

Run: `python -c "import re,yaml; s=open('.github/workflows/bootstrap.yml.jinja').read(); s=re.sub(r'{%.*?%}','',s); yaml.safe_load(s)"`
Expected: no error (the file is valid YAML once jinja tags are stripped). Full render + actionlint happens in Task 6.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/bootstrap.yml.jinja
git commit -m "feat(bootstrap): self-configure auto-merge + branch protection for Renovate"
```

---

## Task 5: Docs + class-sweep for stale "dependabot" references

Updates the README secrets note, sweeps the entire template for now-stale `dependabot` references (fix-the-class discipline), and reclassifies each hit.

**Files:**
- Modify: `README.md.jinja` (GitHub secrets section, around `README.md.jinja:135-149`)
- Modify: `CLAUDE.md.jinja` (line 103 — the one prose reference)

**Pre-enumerated `dependabot` class** (from `grep -rniI 'dependabot'`, excluding `.git`/`docs/superpowers`): four hits — three in `bootstrap.yml.jinja` (lines 4, 6, 18) are **already removed by Task 4's full rewrite**; the only remaining prose hit is `CLAUDE.md.jinja:103`. Task 2 already deleted the config file itself. So this task fixes exactly two files (README + CLAUDE.md).

- [ ] **Step 1: Fix the `CLAUDE.md.jinja` prose reference**

In `CLAUDE.md.jinja:103`, replace:

```markdown
Trivial exceptions: pure typo fixes and automated dependency bumps (Dependabot / Renovate) may skip the issue.
```

with:

```markdown
Trivial exceptions: pure typo fixes and automated dependency bumps (Renovate) may skip the issue.
```

- [ ] **Step 2: Update the README GitHub-secrets note**

In `README.md.jinja`, replace the `RELEASE_TOKEN` table row (`README.md.jinja:141`) and add a one-line note after the table. Change the row to:

```markdown
| `RELEASE_TOKEN` | `release.yml`, `copier-update.yml`, `renovate.yml`, `bootstrap.yml` | Fine-grained PAT at <https://github.com/settings/personal-access-tokens/new> with `contents: write`, `pull_requests: write`, and `administration: write` (bootstrap sets branch protection + auto-merge). Scoped to this repo. |
```

And immediately after the closing ```` ``` ```` of the `gh secret set` block (`README.md.jinja:149`), add:

```markdown
> Dependency updates are handled by **Renovate** (`renovate.yml`), which reuses
> `RELEASE_TOKEN`. It maintains `uv.lock` and auto-merges patch/minor bumps once
> the `CI Success` check is green; `bootstrap.yml` enables auto-merge and branch
> protection on first push. GitHub Actions are updated in the copier template
> and arrive via `copier update`, not per-repo.
```

- [ ] **Step 3: Re-run the sweep to confirm no stale references**

Run: `grep -rniI 'dependabot' . --exclude-dir=.git --exclude-dir=docs/superpowers --exclude-dir=.worktrees`
Expected: **no output**. (If the render `/tmp/smoke` dir is inside the repo, exclude it too.) Any remaining hit is an un-migrated reference — fix it before proceeding.

- [ ] **Step 4: Commit**

```bash
git add README.md.jinja CLAUDE.md.jinja
git commit -m "docs(deps): document Renovate + RELEASE_TOKEN scope; remove stale dependabot references"
```

(No `docs/**` files change in this task, so the `mkdocs build --strict` gate is not needed here — it runs as part of Task 6's full render only if a docs file changed elsewhere.)

---

## Task 6: Full render-gate integration verification

Runs the template's own gate on a real render — both `enable_structural_gate` values — to prove the aggregate job's conditional `needs:` is valid, all new workflows parse, and the generated project's gate still passes.

**Files:** none (verification only).

- [ ] **Step 1: Ensure everything is committed**

Run: `git status --short`
Expected: clean (all prior tasks committed; copier renders from the index).

- [ ] **Step 2: Render with the smoke answers (structural gate ON) and run the gate**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --all-groups
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ tests/ && uv run pytest -x -q
cd -
```
Expected: all green.

- [ ] **Step 3: Assert the rendered dependency automation is correct**

```bash
test -f /tmp/smoke/renovate.json
test -f /tmp/smoke/.github/workflows/renovate.yml
test ! -f /tmp/smoke/.github/dependabot.yml
test ! -f /tmp/smoke/.github/renovate.json            # upstream config must NOT render
test ! -f /tmp/smoke/.github/workflows/template-renovate.yml
grep -q 'CI Success' /tmp/smoke/.github/workflows/ci.yml
npx --yes --package renovate -- renovate-config-validator /tmp/smoke/renovate.json
python -c "import yaml; yaml.safe_load(open('/tmp/smoke/.github/workflows/renovate.yml'))"
python -c "import yaml; yaml.safe_load(open('/tmp/smoke/.github/workflows/bootstrap.yml'))"
```
Expected: every `test`/`grep` passes silently, validator prints success, YAML parses. If `renovate.yml` still contains a literal `{{` or `${{`-without-raw artifact, the `{% raw %}` wrapping was missed — fix Task 2/Task 4.

- [ ] **Step 4: Verify the aggregate gate is valid with the structural gate OFF**

The smoke answers set `enable_structural_gate` on; render once more forcing it off to prove `needs:` doesn't reference a missing `structure` job:

```bash
rm -rf /tmp/smoke-nostruct
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml \
  --data enable_structural_gate=false . /tmp/smoke-nostruct
python -c "import yaml; d=yaml.safe_load(open('/tmp/smoke-nostruct/.github/workflows/ci.yml')); n=d['jobs']['ci-success']['needs']; assert 'structure' not in n, n; assert 'lint' in n; print('needs OK:', n)"
```
Expected: `needs OK: ['lint', 'typecheck', 'test', 'audit', 'secrets', 'vale']` (no `structure`). If `enable_structural_gate` is not an overridable copier answer, instead confirm via the smoke render that when `structure` is absent from `jobs`, it is also absent from `ci-success.needs`.

- [ ] **Step 5: Run the upstream regex self-test once more**

Run: `uv run --no-project --with pytest -- pytest scripts/tests/test_renovate_custom_manager.py -q`
Expected: PASS (guards against any Task-5 edit drifting the config).

- [ ] **Step 6: Final commit (if any fix-ups were needed) and open the PR**

Create the tracking issue first (every PR closes an issue), then the PR with `Closes #N`. Do not merge (human-only). PR body must note the two manual prerequisites (RELEASE_TOKEN scope + template-repo secret) and that the first downstream `copier update` PR self-configures on first push to main.

```bash
git push -u origin docs/renovate-dependency-automation-spec
gh pr create --fill
```

---

## Post-merge confirmation (spec Validation — not blocking this PR)

After template release + first downstream `copier update`:
1. Confirm the upstream `Renovate (template)` run detects the jinja Action pins (check its logs / Dependency Dashboard) — this is the live equivalent of Task 1's offline test.
2. On the first downstream Renovate run: a `dev`-group (PEP 735 `[dependency-groups]`) dependency updates and `uv.lock` regenerates cleanly (proves the 43.59.0 fix); a patch/minor PR auto-merges once `CI Success` is green; a major PR stays open.
