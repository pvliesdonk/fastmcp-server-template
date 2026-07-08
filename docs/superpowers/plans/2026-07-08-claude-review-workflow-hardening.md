# Claude review-workflow hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four `claude-review` bot complaints (inline comments, gate-running, "custom command", commit-on-mention) and make the review depend on CI passing — in both the `.jinja` (downstream) and the template's own non-`.jinja` workflows.

**Architecture:** Realign the `@claude` responder to canonical write permissions; add the canonical `claude_args` inline-comment/investigation allow-list plus a `uv` env and a `wait-for-ci` gating job to the reviewer; add a `REVIEW.md` scoping the reviewer away from reproducing CI; document the CI dependency in the generated `CLAUDE.md`.

**Tech Stack:** GitHub Actions YAML, Jinja2 (copier templates), `anthropics/claude-code-action@v1`, `gh` CLI, `uv`.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-07-08-claude-review-workflow-hardening-design.md`. Closes issue **#242**.
- Every `.jinja` change has a **non-`.jinja` twin** in this repo's own `.github/workflows/` — change both in the same task (fix the class, not the instance).
- Wait-for-CI target: workflow **`ci.yml`** downstream (`.jinja`), workflow **`template-ci.yml`** in this repo (non-`.jinja`).
- Pin action versions to match existing template usage: `actions/checkout@v7`, `astral-sh/setup-uv@v8.2.0`, `actions/cache@v6`. Python `3.12` for the reviewer env (mirrors `ci.yml.jinja` lint job).
- `{% raw %}…{% endraw %}` wraps every `${{ … }}` GitHub expression inside `.jinja` files (copier renders `{{ }}`); non-`.jinja` files use bare `${{ … }}`.
- Reviewer keeps `contents: read` (it must never commit); only the `@claude` responder gets `contents: write`.
- Commit messages: Conventional Commits; end with the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.
- Verification is render + YAML-parse + `template-ci`, then a live PR (workflows cannot be unit-tested locally). Do not claim the bot behaviors are fixed until the live-PR step (Task 6) is observed.

---

### Task 1: `@claude` responder — canonical write permissions

**Files:**
- Modify: `.github/workflows/claude.yml.jinja` (permissions block, ~lines 27-32)
- Modify: `.github/workflows/claude.yml` (permissions block, same block)

**Interfaces:**
- Produces: an `@claude` responder that can post inline PR comments (`pull-requests: write`) and commit fixes (`contents: write`). No later task depends on its internals.

- [ ] **Step 1: Edit both files' permissions blocks**

In **both** `.github/workflows/claude.yml.jinja` and `.github/workflows/claude.yml`, change the `permissions:` block from:

```yaml
    permissions:
      contents: read
      pull-requests: read
      issues: read
      id-token: write
      actions: read # Required for Claude to read CI results on PRs
```

to:

```yaml
    permissions:
      contents: write        # Commit fixes when @claude is asked to fix something
      pull-requests: write   # Post inline review comments
      issues: write          # Update issue/PR comments
      id-token: write
      actions: read # Required for Claude to read CI results on PRs
```

Leave the `if:` fork-guard, `additional_permissions`, and all other content unchanged.

- [ ] **Step 2: Verify the non-`.jinja` file is valid YAML**

Run: `uv run --no-project --with pyyaml python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/claude.yml')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Verify both files now grant write**

Run: `grep -c "contents: write" .github/workflows/claude.yml .github/workflows/claude.yml.jinja`
Expected: each file reports `1`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/claude.yml .github/workflows/claude.yml.jinja
git commit -m "fix(claude): grant @claude responder write perms for inline comments + commits

Refs #242

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `REVIEW.md` — scope the reviewer away from reproducing CI

**Files:**
- Create: `REVIEW.md.jinja` (renders to `REVIEW.md` downstream)
- Create: `REVIEW.md` (this repo's own reviewer)

**Interfaces:**
- Produces: a repo-root `REVIEW.md` read by the reviewer as highest-priority instructions. Task 3's `REVIEW.md`-based scoping (complaint #2) depends on this file existing.

- [ ] **Step 1: Create `REVIEW.md.jinja`**

Create `REVIEW.md.jinja` with exactly this content:

```markdown
# Review instructions

<!-- DOMAIN-REVIEW-START -->
<!-- Add project-specific review rules here. Kept across copier update. -->
<!-- DOMAIN-REVIEW-END -->

<!-- ===== TEMPLATE-OWNED BELOW — DO NOT EDIT; OVERWRITTEN ON COPIER UPDATE ===== -->

## Don't reproduce CI

CI already enforces the full gate: ruff (lint + format), mypy, the pytest
matrix, dependency audit, secret scan, Vale prose, and — when enabled — the
structural gate. Do **not** report findings those checks already gate, and do
**not** re-run the gate. When you need a check's result, read it from CI
(`gh run view`) instead of running it yourself.

## Investigate narrowly

You may run a single targeted command to confirm one specific hypothesis (for
example, one test or `mypy` on one file). This is for verifying a finding — not
for re-executing the suite.

## Focus

Report correctness bugs, security issues, and regressions introduced by this
diff. Behavior claims need a `file:line` citation in the source, not an
inference from naming.

## Converge

After the first review of a PR, suppress repeat nits and post Important
findings only. A one-line fix should not reach round seven on style.
```

- [ ] **Step 2: Create the template's own `REVIEW.md`**

Create `REVIEW.md` with the **same** content as Step 1 (identical bytes — the template dogfoods its own reviewer).

- [ ] **Step 3: Verify both exist and match**

Run: `diff REVIEW.md REVIEW.md.jinja && echo IDENTICAL`
Expected: `IDENTICAL` (no jinja expressions in this file, so the two are byte-identical)

- [ ] **Step 4: Commit**

```bash
git add REVIEW.md REVIEW.md.jinja
git commit -m "feat(review): add REVIEW.md scoping the reviewer away from re-running CI

Refs #242

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Reviewer — inline-comment allow-list, uv env, wait-for-CI gate

**Files:**
- Modify: `.github/workflows/claude-code-review.yml.jinja` (rewrite the job structure)
- Modify: `.github/workflows/claude-code-review.yml` (same, wait target `template-ci.yml`)

**Interfaces:**
- Consumes: `REVIEW.md` from Task 2 (read automatically by the reviewer at repo root).
- Produces: a reviewer that (a) posts inline comments via the granted `mcp__github_inline_comment__create_inline_comment` tool, (b) can run targeted `uv run` checks, (c) reads CI results, and (d) only runs when the CI workflow concluded `success` for the PR head SHA.

- [ ] **Step 1: Rewrite `.github/workflows/claude-code-review.yml.jinja`**

Replace the file's `jobs:` section so there are two jobs — `wait-for-ci` (gate) and `claude-review` (`needs` it). Keep the existing `name:`, `on:` block, and the fork-guard comment. The full file becomes:

```yaml
name: Claude Code Review

on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]

jobs:
  wait-for-ci:
    # Skip PRs from forks: GitHub does not expose repository secrets
    # (including CLAUDE_CODE_OAUTH_TOKEN) to workflows running in fork-PR
    # context, regardless of maintainer approval. Running anyway produces
    # a hard-failing check on every external contribution.
    if: {% raw %}${{ github.event.pull_request.head.repo.full_name == github.repository }}{% endraw %}
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      actions: read
    outputs:
      ci_passed: {% raw %}${{ steps.wait.outputs.ci_passed }}{% endraw %}
    steps:
      - name: Wait for CI to conclude on this PR head
        id: wait
        env:
          GH_TOKEN: {% raw %}${{ secrets.GITHUB_TOKEN }}{% endraw %}
          REPO: {% raw %}${{ github.repository }}{% endraw %}
          HEAD_SHA: {% raw %}${{ github.event.pull_request.head.sha }}{% endraw %}
        run: |
          set -euo pipefail
          # Gate the review on the CI workflow: only review code the gate
          # accepted. Poll the CI run for THIS PR head SHA (not github.sha,
          # which is the merge commit) until it completes; tolerate the
          # not-yet-created race by looping. Gate on the run *conclusion*
          # so CI's continue-on-error 3.14 matrix job never blocks.
          deadline=$(( SECONDS + 25 * 60 ))
          conclusion=""
          while [ "$SECONDS" -lt "$deadline" ]; do
            runs=$(gh api "repos/${REPO}/actions/workflows/ci.yml/runs?head_sha=${HEAD_SHA}&per_page=1" 2>/dev/null || echo '{}')
            status=$(echo "$runs" | jq -r '.workflow_runs[0].status // empty')
            conclusion=$(echo "$runs" | jq -r '.workflow_runs[0].conclusion // empty')
            if [ "$status" = "completed" ]; then
              break
            fi
            echo "CI status: ${status:-not-found-yet}; waiting 20s..."
            sleep 20
          done
          if [ "$conclusion" = "success" ]; then
            echo "ci_passed=true" >> "$GITHUB_OUTPUT"
            echo "CI passed — review will run."
          else
            echo "ci_passed=false" >> "$GITHUB_OUTPUT"
            echo "CI did not pass (conclusion=${conclusion:-timeout}) — skipping review."
          fi

  claude-review:
    needs: wait-for-ci
    if: {% raw %}${{ needs.wait-for-ci.outputs.ci_passed == 'true' }}{% endraw %}
    runs-on: ubuntu-latest
    permissions:
      contents: read          # Reviewer reads code; it must never commit
      pull-requests: write     # Post inline review comments
      issues: read
      id-token: write
      actions: read            # Read CI results instead of re-running them
    steps:
      - name: Checkout repository
        uses: actions/checkout@v7
        with:
          fetch-depth: 1

      - name: Install uv
        uses: astral-sh/setup-uv@v8.2.0
        with:
          version: "latest"

      - name: Cache Python interpreter
        uses: actions/cache@v6
        with:
          path: ~/.local/share/uv/python
          key: uv-python-3.12-{% raw %}${{ runner.os }}{% endraw %}

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        # Gives the reviewer a working venv so its targeted `uv run` checks
        # (freedom to investigate one finding) actually execute. REVIEW.md
        # tells it not to re-run the full gate.
        run: uv sync --all-extras --all-groups

      - name: Run Claude Code Review
        id: claude-review
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: {% raw %}${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}{% endraw %}
          plugin_marketplaces: 'https://github.com/anthropics/claude-code.git'
          plugins: 'code-review@claude-code-plugins'
          # `--comment` tells the plugin to actually post (without it, the plugin
          # runs the full review and stops silently — burning ~$3/PR for no output).
          prompt: '/code-review:code-review --comment {% raw %}${{ github.repository }}{% endraw %}/pull/{% raw %}${{ github.event.pull_request.number }}{% endraw %}'
          # Surface progress so a silent failure is visible.
          track_progress: true
          display_report: true
          # Grant the inline-comment tool (NOT in the default allow-set — this is
          # what lets the reviewer post inline), gh read tools to read CI results,
          # and scoped `uv run` for targeted investigation (REVIEW.md sets norms).
          claude_args: |
            --allowedTools "mcp__github_inline_comment__create_inline_comment,Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*),Bash(gh run view:*),Bash(gh run list:*),Bash(uv run pytest:*),Bash(uv run mypy:*),Bash(uv run ruff:*)"
          # See https://github.com/anthropics/claude-code-action/blob/main/docs/usage.md
```

- [ ] **Step 2: Rewrite `.github/workflows/claude-code-review.yml` (non-`.jinja`)**

Create the same two-job structure in the non-`.jinja` file, with these differences: no `{% raw %}` wrappers (bare `${{ … }}`), the wait targets **`template-ci.yml`**, and the token line stays `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`. The `gh api` line becomes:

```bash
            runs=$(gh api "repos/${REPO}/actions/workflows/template-ci.yml/runs?head_sha=${HEAD_SHA}&per_page=1" 2>/dev/null || echo '{}')
```

Everything else (permissions blocks, uv setup, plugin inputs, `claude_args`) is identical to Step 1 with `${{ … }}` unwrapped.

- [ ] **Step 3: Verify the non-`.jinja` file is valid YAML**

Run: `uv run --no-project --with pyyaml python -c "import yaml; d=yaml.safe_load(open('.github/workflows/claude-code-review.yml')); assert set(d['jobs'])=={'wait-for-ci','claude-review'}; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Verify the inline-comment tool grant is present in both files**

Run: `grep -c "mcp__github_inline_comment__create_inline_comment" .github/workflows/claude-code-review.yml .github/workflows/claude-code-review.yml.jinja`
Expected: each file reports `1`

- [ ] **Step 5: Verify each file waits on the correct CI workflow**

Run: `grep -o "workflows/[a-z-]*\.yml/runs" .github/workflows/claude-code-review.yml .github/workflows/claude-code-review.yml.jinja`
Expected: the non-`.jinja` line shows `workflows/template-ci.yml/runs`; the `.jinja` line shows `workflows/ci.yml/runs`

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/claude-code-review.yml .github/workflows/claude-code-review.yml.jinja
git commit -m "fix(claude-review): grant inline-comment tool, add uv env + CI-pass gate

Adds the canonical mcp__github_inline_comment__create_inline_comment grant
(the missing piece behind 'unable to create inline comments'), a uv venv +
scoped uv/gh allow-list for targeted investigation, and a wait-for-ci job so
the review only runs once CI concludes success.

Refs #242

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Document the CI dependency in the generated `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md.jinja` (a template-owned section, not a `DOMAIN` block)

**Interfaces:**
- Produces: a one-line contributor expectation. No task depends on it.

- [ ] **Step 1: Find the template-owned Conventions/CI area**

Run: `grep -n "Conventional commits\|TEMPLATE-OWNED\|## Conventions" CLAUDE.md.jinja`
Expected: locates the template-owned `## Conventions` section (below the `TEMPLATE-OWNED SECTIONS BELOW` banner).

- [ ] **Step 2: Add the expectation line**

Immediately after the `## Conventions` bullet list in `CLAUDE.md.jinja`, add this paragraph:

```markdown
The automated Claude review runs **only after CI passes** — if CI is red, no
review is posted. Fix CI and push; the review runs on the next green run.
```

- [ ] **Step 3: Verify the line is present and inside the template-owned region**

Run: `grep -n "only after CI passes" CLAUDE.md.jinja`
Expected: one match, at a line number greater than the `TEMPLATE-OWNED SECTIONS BELOW` banner line (confirm by also running `grep -n "TEMPLATE-OWNED SECTIONS BELOW" CLAUDE.md.jinja`).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md.jinja
git commit -m "docs(claude): note review runs only after CI passes

Refs #242

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Render gate — prove the template still renders and its gate passes

**Files:** none modified (integration verification of Tasks 1-4)

**Interfaces:**
- Consumes: all prior tasks' files.
- Produces: confidence that rendered output is valid and the generated project's gate is green.

- [ ] **Step 1: Render the template from HEAD**

Run:
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```
Expected: render completes with no error; note copier reads the git index, so all prior commits (Tasks 1-4) must be committed first.

- [ ] **Step 2: Confirm the rendered files exist and are valid YAML/Markdown**

Run:
```bash
test -f /tmp/smoke/REVIEW.md && echo "REVIEW.md OK"
uv run --no-project --with pyyaml python -c "import yaml; [yaml.safe_load(open('/tmp/smoke/.github/workflows/'+f)) for f in ('claude.yml','claude-code-review.yml')]; print('workflows OK')"
grep -q "only after CI passes" /tmp/smoke/CLAUDE.md && echo "CLAUDE.md note OK"
grep -q "workflows/ci.yml/runs" /tmp/smoke/.github/workflows/claude-code-review.yml && echo "wait target OK"
grep -q "mcp__github_inline_comment__create_inline_comment" /tmp/smoke/.github/workflows/claude-code-review.yml && echo "inline grant OK"
```
Expected: `REVIEW.md OK`, `workflows OK`, `CLAUDE.md note OK`, `wait target OK`, `inline grant OK`

- [ ] **Step 3: Run the generated project's gate**

Run:
```bash
cd /tmp/smoke
uv sync --all-extras --all-groups
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ tests/ && uv run pytest -x -q
```
Expected: all pass (this change touches no Python; the gate confirms the render is intact).

- [ ] **Step 4: No commit** (verification only). Return to the repo dir: `cd -`.

---

### Task 6: Live-PR verification (the real gate)

**Files:** none — behavioral verification that cannot be done locally.

**Interfaces:**
- Consumes: the merged/pushed workflow changes.
- Produces: observed evidence the four complaints are resolved. **Do not claim the fix works before this step.**

- [ ] **Step 1: Push the branch and open the PR** (see Execution Handoff — the PR closes #242).

- [ ] **Step 2: Observe the reviewer on the PR**, confirming in order:
  - the `wait-for-ci` job waits, and `claude-review` is **skipped** while CI is red / runs only once CI is green;
  - the reviewer **posts inline comments** (proves the `mcp__github_inline_comment__create_inline_comment` grant is the path the plugin uses — if inline comments still fail, capture the run log; the plugin may post via a different tool that then needs allow-listing);
  - the reviewer **does not** emit the "couldn't run pytest/ruff/mypy" lament (proves REVIEW.md scoping).

- [ ] **Step 3: Observe the responder** — comment `@claude` asking for a trivial fix on the PR; confirm it can post an inline comment and push a commit (proves Task 1 write perms).

- [ ] **Step 4: Record the observations** in the PR thread. If any check fails, treat it as a design-gap signal (return to the spec), not a one-off patch.

---

## Self-Review

**Spec coverage:**
- §1 responder write perms → Task 1 ✓
- §2 reviewer allow-list + actions:read + uv env → Task 3 ✓
- §2d wait-for-ci gate + failure modes (SHA, race, self-deadlock, matrix, timeout, fail, never-ran) → Task 3 Step 1 poll ✓
- §3 REVIEW.md.jinja (DOMAIN sentinel, template-owned) → Task 2 ✓
- §4 CLAUDE.md CI-dependency line → Task 4 ✓
- copier.yml → no change required (spec §copier wiring) ✓
- fix-the-class (non-`.jinja` twins + template REVIEW.md) → Tasks 1-3 both files ✓
- Testing/verification plan → Tasks 5 (render gate) + 6 (live PR) ✓

**Placeholder scan:** every workflow/markdown block is complete copy-paste content; no TBD/TODO; the only conditional (non-`.jinja` differences) is resolved explicitly in Task 3 Step 2.

**Type/name consistency:** job names `wait-for-ci` / `claude-review`, output `ci_passed`, and the `needs.wait-for-ci.outputs.ci_passed == 'true'` gate are used identically across Task 3 and the verification greps. Wait target `ci.yml` (jinja) vs `template-ci.yml` (non-jinja) is stated consistently in Global Constraints, Task 3, and the greps.
