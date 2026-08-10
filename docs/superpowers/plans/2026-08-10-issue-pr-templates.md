# Issue/PR Templates + Contributing Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship GitHub issue forms, a PR template, a contributing guide, and label plumbing to every downstream via the copier template, with the template repo dogfooding the same files.

**Architecture:** Seven content files are plain (no Jinja) so they are one source shared verbatim by this repo and downstream — GitHub uses them directly here, and copier copies them to every downstream. Label existence is ensured two ways: extend `bootstrap.yml.jinja` for downstream, and add a new `_exclude`d `template-labels.yml` for this repo. `CLAUDE.md.jinja`'s contributing + decay sections become pointers to the new single sources.

**Tech Stack:** GitHub Issue Forms (YAML), Markdown, GitHub Actions (`gh label create`), Copier templates.

## Global Constraints

- Copier renders from the git index, not the working tree: **commit before rendering**, then render with `--vcs-ref=HEAD`. The render command in every task is:

  ```bash
  rm -rf /tmp/smoke
  uv run --no-project --with copier copier copy --trust --defaults \
    --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
  ```

- **Hygiene check before anything writes into the render tree** (`uv sync` and `vale sync` leave files behind that the guard reports as violations):

  ```bash
  python3 scripts/check_render_hygiene.py /tmp/smoke
  ```

  If `uv sync`/`vale sync` were already run in `/tmp/smoke`, re-render into a fresh directory and check that instead.

- The new content files are **plain** (no `.jinja` suffix, no `{{ }}`). Do not add Jinja to them.
- The four issue forms are repo-agnostic; phrasing uses "this repo" contextually so it is correct for both this repo and downstream.
- The `decay` form supersedes the inline decay block at `CLAUDE.md.jinja:89`; the `CONTRIBUTING.md` supersedes the "Contributing fixes upstream" routing at `CLAUDE.md.jinja:258`. Both CLAUDE.md.jinja blocks become pointers.
- Label set is minimal: `bug`, `feature`, `decay`, `question`. No `triage`.
- Pre-commit `check yaml` and `end-of-file-fixer` hooks will lint/fix the new YAML and markdown — let them run on commit.

---

## Task 0: Create the feature branch

**Files:** none.

**Interfaces:** Produces a branch off `main` (which includes the spec commit `76ce362`) for all subsequent work.

- [ ] **Step 1: Create and switch to the branch**

Run:
```bash
git checkout main && git pull --ff-only origin main
git checkout -b feat/issue-pr-templates
```

- [ ] **Step 2: Verify branch base is current**

Run: `git log --oneline -1`
Expected: `76ce362 docs(spec): issue/PR templates + contributing guide design` (or newer on `main` — if `main` advanced, the spec commit is included via the branch point).

---

## Task 1: Issue forms + config.yml

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug-report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature-request.yml`
- Create: `.github/ISSUE_TEMPLATE/decay.yml`
- Create: `.github/ISSUE_TEMPLATE/question.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`

**Interfaces:**
- Produces: the four issue forms, each with a top-level `labels:` referencing `bug`/`feature`/`decay`/`question`. The labels themselves are created in Task 4. `config.yml` disables blank issues.

- [ ] **Step 1: Create `.github/ISSUE_TEMPLATE/bug-report.yml`**

```yaml
name: Bug report
description: >
  Something isn't working as expected. See CONTRIBUTING.md for what makes a
  useful bug report. Do not claim a cause you did not verify.
title: "[Bug]: "
labels: ["bug"]
body:
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: One sentence — expected vs actual.
      placeholder: "A one-liner: 'expected X, got Y.'"
    validations:
      required: true
  - type: textarea
    id: observed
    attributes:
      label: Observed
      description: >
        Describe what you actually saw. Paste the real error text or trace —
        not a summary of it. Include where it occurred.
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected
      description: What should have happened.
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Reproduction
      description: >
        Only include steps you actually ran and the version/commit you
        actually checked.
    validations:
      required: true
  - type: textarea
    id: suspected-cause
    attributes:
      label: Suspected cause
      description: >
        Do **not** claim a cause you did not verify. If you haven't checked,
        say so, mark the line `[unverified]`, and add the sentence "I have
        not verified the cause." If you did check, write `[verified: how]`.
    validations:
      required: false
  - type: textarea
    id: open-questions
    attributes:
      label: Open questions / scope
      description: >
        Unknowns the implementer should verify (mark each `[unverified]`).
        What this issue is *not* about.
    validations:
      required: false
```

- [ ] **Step 2: Create `.github/ISSUE_TEMPLATE/feature-request.yml`**

```yaml
name: Feature request
description: >
  Suggest a new feature or enhancement. Describe the problem, not a
  solution. See CONTRIBUTING.md for what makes a useful request.
title: "[Feature]: "
labels: ["feature"]
body:
  - type: textarea
    id: problem
    attributes:
      label: What problem does this solve?
      description: >
        Describe the problem or unmet need — not a solution. Who hits it,
        and when?
    validations:
      required: true
  - type: textarea
    id: desired-outcome
    attributes:
      label: Desired outcome
      description: Describe the outcome, not how to implement it.
    validations:
      required: true
  - type: textarea
    id: implementation-ideas
    attributes:
      label: Implementation ideas
      description: >
        Non-binding starting points only. This issue does not prescribe an
        implementation.
    validations:
      required: false
```

- [ ] **Step 3: Create `.github/ISSUE_TEMPLATE/decay.yml`**

```yaml
name: Decay / structural debt
description: >
  An observation of structural decay worth refactoring later — not a bug,
  not a feature. Constrain this to decay that will compound, not anything
  imperfect. See CONTRIBUTING.md.
title: "[Decay]: "
labels: ["decay"]
body:
  - type: textarea
    id: what
    attributes:
      label: What
      description: The structural problem in one sentence.
    validations:
      required: true
  - type: textarea
    id: where
    attributes:
      label: Where
      description: File/symbol and the metric or observation that flagged it.
    validations:
      required: true
  - type: textarea
    id: why-it-compounds
    attributes:
      label: Why it compounds
      description: What gets harder or riskier if it's left.
    validations:
      required: true
  - type: textarea
    id: suggested-direction
    attributes:
      label: Suggested direction
      description: A starting point, not a prescribed refactor.
    validations:
      required: false
```

- [ ] **Step 4: Create `.github/ISSUE_TEMPLATE/question.yml`**

```yaml
name: Question / support
description: >
  Ask a question or request support. Keeps these out of the bug and
  feature queues.
title: "[Question]: "
labels: ["question"]
body:
  - type: textarea
    id: question
    attributes:
      label: Question
    validations:
      required: true
  - type: textarea
    id: tried
    attributes:
      label: What I've already tried
    validations:
      required: false
```

- [ ] **Step 5: Create `.github/ISSUE_TEMPLATE/config.yml`**

```yaml
blank_issues_enabled: false
```

- [ ] **Step 6: Commit (copier renders from the index)**

```bash
git add .github/ISSUE_TEMPLATE/
git commit -m "feat(templates): add issue forms (bug, feature, decay, question) + config"
```

- [ ] **Step 7: Render locally**

Run:
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```

- [ ] **Step 8: Check render hygiene (before any sync)**

Run: `python3 scripts/check_render_hygiene.py /tmp/smoke`
Expected: PASS, no violations.

- [ ] **Step 9: Verify the five files rendered verbatim**

Run:
```bash
ls /tmp/smoke/.github/ISSUE_TEMPLATE/
```
Expected: `bug-report.yml  config.yml  decay.yml  feature-request.yml  question.yml`

Run:
```bash
grep -c 'labels:' /tmp/smoke/.github/ISSUE_TEMPLATE/bug-report.yml \
  /tmp/smoke/.github/ISSUE_TEMPLATE/feature-request.yml \
  /tmp/smoke/.github/ISSUE_TEMPLATE/decay.yml \
  /tmp/smoke/.github/ISSUE_TEMPLATE/question.yml
```
Expected: each file prints `1`.

Run: `cat /tmp/smoke/.github/ISSUE_TEMPLATE/config.yml`
Expected:
```yaml
blank_issues_enabled: false
```

---

## Task 2: PR template

**Files:**
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

**Interfaces:**
- Produces: the PR template, plain markdown, generic (no substitution). Downstream and this repo share it verbatim.

- [ ] **Step 1: Create `.github/PULL_REQUEST_TEMPLATE.md`**

```markdown
## Closes / Refs

Closes #N  (or `Refs #N` if not closing)

> **No orphan PRs.** Create the issue first if none exists. Pure typo fixes
> and Renovate dependency bumps excepted.

## What & why

One or two sentences, in observation terms: what changed, and why.

## What this PR deliberately does NOT do

List each deferral with its tracking issue number. A change that says what
it deliberately did not do is easier to trust than one that appears to have
found nothing.

- (deferral) — #N

## Local review

- [ ] Ran a local code-review pass on the cumulative diff before `gh pr create`.

## Docs impact

- [ ] `README.md`
- [ ] `docs/` site pages
- [ ] `docs/design/`
- [ ] Inline docstrings

**Rule: code without matching docs is incomplete.**
```

- [ ] **Step 2: Commit**

```bash
git add .github/PULL_REQUEST_TEMPLATE.md
git commit -m "feat(templates): add pull request template"
```

- [ ] **Step 3: Render and verify**

Run:
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```

Run: `python3 scripts/check_render_hygiene.py /tmp/smoke`
Expected: PASS.

Run: `test -f /tmp/smoke/.github/PULL_REQUEST_TEMPLATE.md && echo OK`
Expected: `OK`

Run: `head -1 /tmp/smoke/.github/PULL_REQUEST_TEMPLATE.md`
Expected: `## Closes / Refs`

---

## Task 3: CONTRIBUTING.md + CLAUDE.md.jinja pointers

**Files:**
- Create: `CONTRIBUTING.md`
- Modify: `CLAUDE.md.jinja` (decay inline block, lines ~89-96)
- Modify: `CLAUDE.md.jinja` (Contributing fixes upstream section, lines ~258-262)

**Interfaces:**
- Produces: `CONTRIBUTING.md` as the single source for the issue/PR discipline and the three-tier upstream routing. `CLAUDE.md.jinja`'s decay block and contributing section become pointers.
- Consumes: the issue forms from Task 1 (CONTRIBUTING.md references them) and the decay form (CLAUDE.md.jinja decay block points at it).

- [ ] **Step 1: Create `CONTRIBUTING.md`**

```markdown
# Contributing

Thanks for contributing. This guide covers how to file good issues and pull
requests, and where to send different kinds of fixes. It applies to both
human contributors and automated agents.

## Filing issues

Use the issue templates in `.github/ISSUE_TEMPLATE/`:

- **Bug report** — something isn't working as expected.
- **Feature request** — a new capability or enhancement.
- **Decay / structural debt** — refactor-later observations.
- **Question / support** — questions and support requests.

### Observation, not work order

An issue records what was **observed**. It does not diagnose, design, or
prescribe a fix. An issue that reads like a work order misleads the
implementer into treating imagination as researched fact.

- Describe what you saw — the concrete behaviour, exact error text or trace,
  where it occurred, the version/commit you checked.
- Do not assert a root cause you did not verify.
- Do not propose an architecture or list implementation steps.

### The uncertainty rule

Every cause statement must be marked:

- `[verified: how]` — you checked; here is how.
- `[unverified]` — you have not verified this.

When you have not verified the cause, this sentence is required:

> I have not verified the cause.

The implementer must inherit your doubt, not a false floor of confidence.

### One issue, one observed problem

If you notice a second suspected problem while writing, do not add it to the
body. If you genuinely suspect it shares a code path, add one line under Open
Questions: `[unverified]: <suspected problem> may share this code path`. Open
a separate issue for it.

### Remove before posting

| What you wrote | What to do instead |
|----------------|-------------------|
| "Root cause is X; fix by doing Y" | Cause: `[unverified]` + observed behaviour only |
| Any sentence starting with "Fix by", "We should", "Refactor", "Add a", "The solution is" | Delete the sentence |
| "Import is probably similarly broken" | One Open Questions line: `[unverified]: import may share this path` |
| A cause asserted without a `[verified]` or `[unverified]` marker | Add the marker; add "I have not verified the cause" if unverified |
| An "Additional context" section that introduces new problems | Open a separate issue |
| Implementation steps (a numbered list of code changes) | Remove entirely |

## Pull requests

Every PR must have at least one associated issue. If the work has no issue
yet — a bug found in the wild, an opportunistic cleanup — create the issue
first, then open the PR with `Closes #N` (or `Refs #N`) in the body. A single
PR may close multiple issues (`Closes #A, closes #B`); the rule is "no orphan
PRs", not "one PR per issue". Trivial exceptions: pure typo fixes and
automated dependency bumps (Renovate) may skip the issue.

State what the PR deliberately does **not** do, with each deferral's tracking
issue. A change that says what it left out is easier to trust than one that
appears to have found nothing.

Run a local code-review pass on the cumulative diff before `gh pr create`.
Code without matching docs is incomplete — check `README.md`, the `docs/`
site, `docs/design/`, and inline docstrings.

## Where to send fixes

- **Library-level fix** (anything you'd change in `fastmcp_pvl_core`): open a
  PR on `pvliesdonk/fastmcp-pvl-core`. After merge + release, bump
  `fastmcp-pvl-core` in this project's `pyproject.toml`. (Copier update alone
  won't pick it up unless the template's version constraint in
  `pyproject.toml.jinja` is also bumped.)
- **Template-level fix** (anything template-owned — `Dockerfile`, workflows,
  `server.py` skeleton, `CLAUDE.md` sections): open a PR on
  `pvliesdonk/fastmcp-server-template`. After merge + release, this project
  gets the fix on the next weekly `copier update` cron (or dispatch the
  workflow manually).
- **Domain-only fix** (anything inside a `DOMAIN-*`, `CONFIG-*`, or
  `PROJECT-*` sentinel block, `tools.py`, `resources.py`, `prompts.py`,
  `domain.py`, `tests/`): PR on this repo directly.
```

- [ ] **Step 2: Edit `CLAUDE.md.jinja` — decay inline block → pointer**

Replace this exact text:

```
**Open an issue** using this template:

> **What:** the structural problem in one sentence.
> **Where:** file/symbol and the metric or observation that flagged it.
> **Why it compounds:** what gets harder or riskier if it's left.
> **Suggested direction:** a starting point, not a prescribed refactor.
```

with:

```
**Open an issue** using the **Decay** form (`.github/ISSUE_TEMPLATE/decay.yml`): What / Where / Why it compounds / Suggested direction.
```

(Leave the surrounding "**When you notice decay…**" sentence and the "Constrain issues to **decay that will compound**…" sentence unchanged. Only the quoted template block becomes the pointer.)

- [ ] **Step 3: Edit `CLAUDE.md.jinja` — Contributing fixes upstream section → pointer**

Replace this exact block:

```
## Contributing fixes upstream

- **Library-level fix** (anything you'd change in `fastmcp_pvl_core`): open a PR on `pvliesdonk/fastmcp-pvl-core`. After merge + release, bump `fastmcp-pvl-core` in this project's `pyproject.toml`. (Copier update alone won't pick it up unless the template's version constraint in `pyproject.toml.jinja` is also bumped.)
- **Template-level fix** (anything template-owned — `Dockerfile`, workflows, `server.py` skeleton, `CLAUDE.md` sections): open a PR on `pvliesdonk/fastmcp-server-template`. After merge + release, this project gets the fix on the next weekly `copier update` cron (or dispatch the workflow manually).
- **Domain-only fix** (anything inside a `DOMAIN-*`, `CONFIG-*`, or `PROJECT-*` sentinel block, `tools.py`, `resources.py`, `prompts.py`, `domain.py`, `tests/`): PR on this repo directly.
```

with:

```
## Contributing fixes upstream

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the three-tier routing (library → `fastmcp-pvl-core`, template → `fastmcp-server-template`, domain → this repo), the issue/PR discipline, and the uncertainty rule. CONTRIBUTING.md is the single source; this section is a pointer.
```

- [ ] **Step 4: Commit**

```bash
git add CONTRIBUTING.md CLAUDE.md.jinja
git commit -m "feat(templates): add CONTRIBUTING.md; point CLAUDE.md.jinja at it + decay form"
```

- [ ] **Step 5: Render and verify hygiene**

Run:
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```

Run: `python3 scripts/check_render_hygiene.py /tmp/smoke`
Expected: PASS.

- [ ] **Step 6: Verify CONTRIBUTING.md rendered and CLAUDE.md.jinja edits landed**

Run: `test -f /tmp/smoke/CONTRIBUTING.md && echo OK`
Expected: `OK`

Run: `grep -c "Open an issue" /tmp/smoke/CLAUDE.md`
Expected: `1` (the pointer, not the old quoted template)

Run: `grep "Decay" /tmp/smoke/CLAUDE.md | head -1`
Expected: a line containing "the **Decay** form"

Run: `grep -c "See [\`CONTRIBUTING.md\`]" /tmp/smoke/CLAUDE.md`
Expected: `1`

---

## Task 4: Labels — bootstrap edit + template-labels.yml + _exclude

**Files:**
- Modify: `.github/workflows/bootstrap.yml.jinja` (add four `gh label create` calls to the existing `labels` job run block)
- Create: `.github/workflows/template-labels.yml` (this repo only)
- Modify: `copier.yml` `_exclude` (add the `template-labels.yml` line)

**Interfaces:**
- Consumes: the `labels: ["bug"]` / `["feature"]` / `["decay"]` / `["question"]` from Task 1's forms — these only apply if the labels exist in the repo.
- Produces: downstream label creation (via bootstrap, rendered) and this-repo label creation (via the excluded `template-labels.yml`).

- [ ] **Step 1: Edit `bootstrap.yml.jinja` — add four label-create calls**

Replace this exact block (the `labels` job's run block):

```
        run: |
          gh label create dependencies \
            --color 0366d6 \
            --description "Pull requests that update a dependency" \
            --force
```

with:

```
        run: |
          gh label create dependencies \
            --color 0366d6 \
            --description "Pull requests that update a dependency" \
            --force
          gh label create bug \
            --color d73a4a \
            --description "Something isn't working" \
            --force
          gh label create feature \
            --color a2eeef \
            --description "New feature or request" \
            --force
          gh label create decay \
            --color fbca04 \
            --description "Structural debt worth refactoring later" \
            --force
          gh label create question \
            --color d876e3 \
            --description "Further information is requested" \
            --force
```

(The `env:` block above it with `{% raw %}${{ github.token }}{% endraw %}` is unchanged. Only the `run:` block grows by four `gh label create` calls.)

- [ ] **Step 2: Create `.github/workflows/template-labels.yml` (this repo only)**

```yaml
name: Ensure repository labels

# Creates the issue-form labels this repo's issue templates reference, plus
# the `dependencies` label Renovate applies to its PRs. GitHub silently drops
# labels that don't exist, so the templates' `labels:` only work if these
# exist here.
#
# Idempotent: `--force` converges to the same state on every run. Runs on the
# first push to main that changes this file, and on demand via dispatch.
#
# This workflow is template-repo-only — excluded from downstream copies (see
# `_exclude` in copier.yml). Downstream gets its labels from the `labels` job
# in bootstrap.yml.

on:
  push:
    branches: [main]
    paths:
      - .github/workflows/template-labels.yml
  workflow_dispatch:

permissions:
  issues: write

jobs:
  labels:
    name: Ensure repository labels
    runs-on: ubuntu-latest
    steps:
      - name: Create labels
        env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: ${{ github.repository }}
        run: |
          gh label create bug \
            --color d73a4a \
            --description "Something isn't working" \
            --force
          gh label create feature \
            --color a2eeef \
            --description "New feature or request" \
            --force
          gh label create decay \
            --color fbca04 \
            --description "Structural debt worth refactoring later" \
            --force
          gh label create question \
            --color d876e3 \
            --description "Further information is requested" \
            --force
          gh label create dependencies \
            --color 0366d6 \
            --description "Pull requests that update a dependency" \
            --force
```

- [ ] **Step 3: Edit `copier.yml` `_exclude` — exclude template-labels.yml**

Add this line immediately after the existing `template-renovate.yml` line (line 213):

```
  - ".github/workflows/template-labels.yml"  # this repo's label-ensure — template-repo only
```

The result in context:
```
  - ".github/workflows/template-renovate.yml"  # upstream Renovate runner — template-repo only
  - ".github/workflows/template-labels.yml"  # this repo's label-ensure — template-repo only
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/bootstrap.yml.jinja .github/workflows/template-labels.yml copier.yml
git commit -m "feat(ci): ensure issue-form labels exist (bootstrap for downstream, template-labels for this repo)"
```

- [ ] **Step 5: Render and verify hygiene + exclusion**

Run:
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```

Run: `python3 scripts/check_render_hygiene.py /tmp/smoke`
Expected: PASS.

Run: `test -f /tmp/smoke/.github/workflows/template-labels.yml && echo LEAKED || echo EXCLUDED`
Expected: `EXCLUDED` (the workflow must not appear in the downstream render).

Run: `grep -c "gh label create bug" /tmp/smoke/.github/workflows/bootstrap.yml`
Expected: `1` (the downstream bootstrap carries the new label-create calls).

Run: `grep -c "gh label create dependencies" /tmp/smoke/.github/workflows/bootstrap.yml`
Expected: `1` (the original dependencies label is still there).

---

## Task 5: Full gate on the cumulative render

**Files:** none (verification + fixes only).

**Interfaces:**
- Consumes: all files from Tasks 1-4, now committed and rendered together.

This runs the rendered project's own gate over the full render, the same gate `template-ci` runs. No Python was added, so ruff/mypy/pytest should pass unchanged; the risks are hygiene (already checked per-task) and Vale on `README.md`/`docs` (CONTRIBUTING.md and the issue forms are **not** in the Vale file set).

- [ ] **Step 1: Fresh render (hygiene must run before sync)**

Run:
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
python3 scripts/check_render_hygiene.py /tmp/smoke
```
Expected: hygiene PASS.

- [ ] **Step 2: Vale on the rendered prose**

The Vale version, file set, and glob are extracted from the rendered `ci.yml` — match the version pinned there. Run, from `/tmp/smoke`:

```bash
cd /tmp/smoke
vale sync
vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md
```
Expected: clean (the new files are not in `docs` or `README.md`, so they are not linted; this confirms nothing existing regressed).

- [ ] **Step 3: Generated project's gate**

```bash
cd /tmp/smoke
uv sync --all-extras --all-groups
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ tests/ && uv run pytest -x -q
```
Expected: all pass (no Python changed; this confirms the new non-Python files did not break collection/config).

- [ ] **Step 4: Re-render idempotence check (optional but cheap)**

Confirm a second render is byte-identical to the first (the template CI asserts this; catching a non-determinism early is cheap):

```bash
rm -rf /tmp/smoke2
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke2
diff -r /tmp/smoke /tmp/smoke2 && echo IDENTICAL
```
Expected: `IDENTICAL` (no diff output).

- [ ] **Step 5: If any check above failed, fix and amend**

Fix the offending file, `git add` + `git commit --amend` (or a follow-up commit), and re-render + re-run the failing check. Do not push until all pass.

- [ ] **Step 6: Branch is PR-ready — stop**

Do not open the PR yet. The PR (with its issue) is the next cycle per the project's "Working an issue" and "Pull requests" rules: an issue must exist on GitHub before the PR opens, and the preflight circus must be green before any push. Surface the branch state to the user.

---

## Self-Review

**Spec coverage** (each spec deliverable → task):
- Four issue forms → Task 1 (steps 1-4). ✅
- `config.yml` with `blank_issues_enabled: false` → Task 1 step 5. ✅
- PR template (generic, no substitution) → Task 2. ✅
- `CONTRIBUTING.md` (discipline + three-tier routing) → Task 3 step 1. ✅
- `bootstrap.yml.jinja` label-create calls → Task 4 step 1. ✅
- `template-labels.yml` (excluded) → Task 4 step 2. ✅
- `copier.yml` `_exclude` line → Task 4 step 3. ✅
- `CLAUDE.md.jinja` decay block → pointer (Task 3 step 2) ✅; contributing section → pointer (Task 3 step 3) ✅.
- Render hygiene + full gate → Task 5. ✅
- Label set minimal (no triage) → respected in Task 1 + Task 4. ✅

**Placeholder scan:** no "TBD"/"TODO"/"implement later". Every file step contains full content. ✅

**Type/name consistency:** label names (`bug`/`feature`/`decay`/`question`) and colors (`d73a4a`/`a2eeef`/`fbca04`/`d876e3`) are identical across the issue forms (Task 1), bootstrap edit (Task 4 step 1), and template-labels.yml (Task 4 step 2). The `dependencies` label color `0366d6` matches the existing bootstrap value. ✅

**Scope:** one PR, one cycle, branched off main. Task 5 stops before opening the PR per project PR rules. ✅
