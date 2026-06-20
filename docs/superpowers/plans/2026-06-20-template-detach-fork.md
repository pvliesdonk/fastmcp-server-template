# Template Detach / Fork Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a documented, mechanical, CI-verified way for a generated project to detach from this copier template and become an independent fork.

**Architecture:** Three changes to the template's *rendered output* and *self-test*: (1) wrap the template-coupled prose in `CLAUDE.md.jinja` in `TEMPLATE-TRACKING` markers so the scrub is one `sed`; (2) add a rendered root-level `FORKING.md.jinja` documenting the detach; (3) add two `template-ci.yml` assertion steps — a marker-balance guard and an end-to-end detach-smoke step that runs the documented commands and verifies the resulting standalone state.

**Tech Stack:** copier (Jinja2 templates), GitHub Actions (inline bash assertions), Markdown.

## Global Constraints

- **copier reads from the git index, not the working tree.** Every local render in this plan uses `--vcs-ref=HEAD` and therefore requires the relevant edits to be **committed first**. Uncommitted changes are silently ignored. (Source: this repo's `CLAUDE.md`, "Making changes".)
- **Local render command** (used verbatim throughout):
  ```bash
  rm -rf /tmp/smoke
  uv run --no-project --with copier copier copy --trust --defaults \
    --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
  ```
- **Branch:** all commits land on `feat/template-detach-fork` (already created; the design spec is its first commit).
- **Commit trailer:** every commit message ends with
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **CI assertion idiom** (match the existing steps in `template-ci.yml`): use `count=$(grep -cE '<pat>' FILE || true)` then `[ "$count" = "N" ] || { echo "::error::..."; exit 1; }`. The `|| true` keeps `bash -e` from aborting at the command substitution when grep matches zero lines.
- **Spec:** `docs/superpowers/specs/2026-06-20-template-detach-fork-design.md`. Issue: #182.
- **Strip set** (a detached fork removes these): `.github/workflows/copier-update.yml`, `.github/workflows/claude.yml`, `.github/workflows/claude-code-review.yml`, `.gemini/`. **Keep set:** `ci.yml`, `codeql.yml`, `coverage-status.yml`, `docs.yml`, `release.yml`.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `CLAUDE.md.jinja` | Modify | Add two `TEMPLATE-TRACKING` marker pairs around the bot-reviewer paragraph and the Shared-Infrastructure / Contributing-fixes-upstream sections. |
| `.github/workflows/template-ci.yml` | Modify | Add marker-balance assertions (Task 1) and a detach-smoke step (Task 3). |
| `FORKING.md.jinja` | Create | Rendered root-level detach guide for generated projects. |

No `copier.yml` change is needed: `FORKING.md.jinja` is an ordinary template file (suffix `.jinja`), so copier renders it automatically and re-renders it on `copier update`. It is intentionally **not** in `_skip_if_exists` (the guide should track template improvements until the fork detaches and deletes it).

---

## Task 1: `TEMPLATE-TRACKING` markers + CI marker-balance guard

**Files:**
- Modify: `CLAUDE.md.jinja` (bot-reviewer paragraph ~line 55; Shared-Infrastructure / Contributing-fixes-upstream sections ~lines 151–166)
- Modify: `.github/workflows/template-ci.yml` (extend the `CLAUDE.md sentinel structure` step, ~lines 69–83)

**Interfaces:**
- Produces: two `<!-- TEMPLATE-TRACKING-START -->` / `<!-- TEMPLATE-TRACKING-END -->` marker pairs in the rendered `CLAUDE.md`, deletable as a `sed` range. Task 2 (FORKING.md) and Task 3 (detach-smoke) both rely on these markers existing and being balanced (exactly 2 of each).

- [ ] **Step 1: Establish the red baseline — render current HEAD and confirm the markers are absent**

Run:
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
grep -cE '^<!-- TEMPLATE-TRACKING-START -->$' /tmp/smoke/CLAUDE.md || true
```
Expected: prints `0` (markers do not exist yet — this is the failing state the guard will catch).

- [ ] **Step 2: Add marker pair 1 around the bot-reviewer paragraph in `CLAUDE.md.jinja`**

Replace this exact block:
```markdown
Trivial exceptions: pure typo fixes and automated dependency bumps (Dependabot / Renovate) may skip the issue.

**Bot reviewers (claude-review, gemini-code-assist) are merge gates, not pair reviewers.** Local review must be complete before the PR opens. If a bot finds anything on first run, the local review was incomplete — that is a discipline failure to investigate, not "address-and-move-on." Run a local code-review pass on the cumulative diff before `gh pr create`; the bots are not a substitute.

## GitHub Review Types
```
with:
```markdown
Trivial exceptions: pure typo fixes and automated dependency bumps (Dependabot / Renovate) may skip the issue.

<!-- TEMPLATE-TRACKING-START -->
**Bot reviewers (claude-review, gemini-code-assist) are merge gates, not pair reviewers.** Local review must be complete before the PR opens. If a bot finds anything on first run, the local review was incomplete — that is a discipline failure to investigate, not "address-and-move-on." Run a local code-review pass on the cumulative diff before `gh pr create`; the bots are not a substitute.
<!-- TEMPLATE-TRACKING-END -->

## GitHub Review Types
```

- [ ] **Step 3: Add marker pair 2 opening before `## Shared Infrastructure` in `CLAUDE.md.jinja`**

Replace this exact line:
```markdown
## Shared Infrastructure
```
with:
```markdown
<!-- TEMPLATE-TRACKING-START -->
## Shared Infrastructure
```

- [ ] **Step 4: Add marker pair 2 closing before the `TEMPLATE-OWNED SECTIONS END` fence**

Replace this exact block:
```markdown
If a conflict marker appears in a copier-update bot PR, the conflict itself often signals a template bug — investigate whether the template's version needs fixing before resolving locally.

<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->
```
with:
```markdown
If a conflict marker appears in a copier-update bot PR, the conflict itself often signals a template bug — investigate whether the template's version needs fixing before resolving locally.
<!-- TEMPLATE-TRACKING-END -->

<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->
```

- [ ] **Step 5: Add the marker-balance guard to `template-ci.yml`**

In `.github/workflows/template-ci.yml`, find the `CLAUDE.md sentinel structure` step and replace these two lines:
```yaml
          grep -qE '^<!-- ===== TEMPLATE-OWNED SECTIONS BELOW' CLAUDE.md || { echo "::error::missing TEMPLATE-OWNED opening fence"; exit 1; }
          grep -qE '^<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->$' CLAUDE.md || { echo "::error::missing TEMPLATE-OWNED closing fence"; exit 1; }
```
with:
```yaml
          grep -qE '^<!-- ===== TEMPLATE-OWNED SECTIONS BELOW' CLAUDE.md || { echo "::error::missing TEMPLATE-OWNED opening fence"; exit 1; }
          grep -qE '^<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->$' CLAUDE.md || { echo "::error::missing TEMPLATE-OWNED closing fence"; exit 1; }
          # TEMPLATE-TRACKING marker pairs (2): one around the bot-reviewer
          # paragraph, one around Shared Infrastructure + Contributing fixes
          # upstream. FORKING.md's detach scrub deletes them as a sed range — a
          # dropped marker would make the scrub delete the wrong span, so the
          # count must stay exact.
          ttstart=$(grep -cE '^<!-- TEMPLATE-TRACKING-START -->$' CLAUDE.md || true)
          ttend=$(grep -cE '^<!-- TEMPLATE-TRACKING-END -->$' CLAUDE.md || true)
          [ "$ttstart" = "2" ] || { echo "::error::expected 2 TEMPLATE-TRACKING-START markers, found $ttstart"; exit 1; }
          [ "$ttend" = "2" ] || { echo "::error::expected 2 TEMPLATE-TRACKING-END markers, found $ttend"; exit 1; }
```

- [ ] **Step 6: Commit (required before re-rendering — copier reads the index)**

```bash
git add CLAUDE.md.jinja .github/workflows/template-ci.yml
git commit -m "feat(scaffold): mark template-tracking CLAUDE.md sections for detach (refs #182)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7: Render and verify the markers are present, balanced, and scrub cleanly (green)**

Run:
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
echo "START=$(grep -cE '^<!-- TEMPLATE-TRACKING-START -->$' /tmp/smoke/CLAUDE.md) END=$(grep -cE '^<!-- TEMPLATE-TRACKING-END -->$' /tmp/smoke/CLAUDE.md)"
# Simulate the scrub on a copy and confirm the right content is gone / kept:
cp /tmp/smoke/CLAUDE.md /tmp/claude-scrubbed.md
sed -i '/<!-- TEMPLATE-TRACKING-START -->/,/<!-- TEMPLATE-TRACKING-END -->/d' /tmp/claude-scrubbed.md
grep -qE '^## Shared Infrastructure$' /tmp/claude-scrubbed.md && echo "BAD: Shared Infrastructure survived" || echo "OK: Shared Infrastructure removed"
grep -qE 'claude-review, gemini-code-assist' /tmp/claude-scrubbed.md && echo "BAD: bot paragraph survived" || echo "OK: bot paragraph removed"
grep -qE '^## GitHub Review Types$' /tmp/claude-scrubbed.md && echo "OK: GitHub Review Types kept" || echo "BAD: GitHub Review Types lost"
grep -qE '^## Conventions$' /tmp/claude-scrubbed.md && echo "OK: Conventions kept" || echo "BAD: Conventions lost"
```
Expected output:
```
START=2 END=2
OK: Shared Infrastructure removed
OK: bot paragraph removed
OK: GitHub Review Types kept
OK: Conventions kept
```
If any line says `BAD`, the marker placement is wrong — fix the relevant edit, amend the commit (`git commit --amend --no-edit`), and re-run this step.

---

## Task 2: `FORKING.md.jinja` detach guide

**Files:**
- Create: `FORKING.md.jinja`

**Interfaces:**
- Consumes: the `TEMPLATE-TRACKING` markers from Task 1 (the Step 3 `sed` command targets them) and the Global-Constraints strip/keep sets.
- Produces: a rendered root `FORKING.md` whose documented commands Task 3's detach-smoke step mirrors exactly.

- [ ] **Step 1: Create `FORKING.md.jinja` with this exact content**

```markdown
# Forking: detaching from the template

This project was generated from the
[`fastmcp-server-template`](https://github.com/pvliesdonk/fastmcp-server-template)
copier template and, by default, **tracks** it: the weekly
`copier-update` workflow opens PRs that pull in template and `fastmcp-pvl-core`
improvements, and `CLAUDE.md` routes fixes back upstream.

A **fork** is different. If you are taking sole ownership of this server, or
want an opinionated variant that no longer follows the fleet, you should
**detach**: stop tracking the template and remove the fleet-wide automation and
guidance that no longer applies. A fork is not a downstream — after detaching,
template and `fastmcp-pvl-core` changes are yours to port manually.

Detaching is mechanical. Run the steps below once, then commit.

## Step 1 — Stop tracking the template

```bash
rm .copier-answers.yml
```

This removes the link copier uses to reattach. The weekly cron that ran
`copier update` is deleted in Step 2.

## Step 2 — Prune template-origin CI and fleet review wiring

```bash
rm -f .github/workflows/copier-update.yml \
      .github/workflows/claude.yml \
      .github/workflows/claude-code-review.yml
rm -rf .gemini
```

What this removes and why:

- `copier-update.yml` — template-update automation; meaningless once detached.
- `claude.yml`, `claude-code-review.yml` — fleet review-bot wiring.
- `.gemini/` — gemini-code-assist fleet scope control.

**Keep** your own CI and release workflows: `ci.yml`, `codeql.yml`,
`coverage-status.yml`, `docs.yml`, and `release.yml`. (`release.yml` still needs
the `RELEASE_TOKEN` secret; only its `copier-update` justification is gone.)

## Step 3 — Scrub template-tracking guidance from `CLAUDE.md`

```bash
sed -i '/<!-- TEMPLATE-TRACKING-START -->/,/<!-- TEMPLATE-TRACKING-END -->/d' CLAUDE.md
```

This deletes the template-coupled sections — the bot-reviewer merge-gate
paragraph, **Shared Infrastructure**, and **Contributing fixes upstream** —
while keeping the fork-neutral contributor guidance (Conventions, the PR
acceptance gates, the Logging Standard, the config contract, GitHub Review
Types). If your fork added its own `.claude/CLAUDE.md`, apply the same scrub
there.

## Step 4 — README cleanup (optional)

These leftover references are harmless but now misleading:

- The **Template** badge at the top of `README.md` (the
  `![Template](https://img.shields.io/badge/dynamic/yaml?...&label=template)`
  entry) points at the now-deleted `.copier-answers.yml`. Remove it.
- In the secrets table, the `RELEASE_TOKEN` row lists `copier-update.yml` as a
  consumer. Drop that workflow from the row.
- The `### \`uv.lock\` refresh after \`copier update\`` subsection no longer
  applies. Remove it.

## You are now standalone

Commit the result:

```bash
git add -A
git commit -m "chore: detach from fastmcp-server-template"
```

Future template or `fastmcp-pvl-core` fixes are no longer delivered
automatically — pull in anything you want by hand.
```

- [ ] **Step 2: Commit (required before rendering)**

```bash
git add FORKING.md.jinja
git commit -m "feat(scaffold): add FORKING.md detach guide (refs #182)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 3: Render and verify `FORKING.md` is produced and Jinja-clean**

Run:
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
test -f /tmp/smoke/FORKING.md && echo "OK: FORKING.md rendered"
# No unrendered Jinja delimiters should remain:
grep -nE '\{\{|\{%' /tmp/smoke/FORKING.md && echo "BAD: unrendered Jinja in FORKING.md" || echo "OK: no Jinja residue"
# The four documented step headings are present:
for h in "## Step 1 — Stop tracking the template" \
         "## Step 2 — Prune template-origin CI and fleet review wiring" \
         "## Step 3 — Scrub template-tracking guidance from \`CLAUDE.md\`" \
         "## Step 4 — README cleanup (optional)"; do
  grep -qF "$h" /tmp/smoke/FORKING.md || echo "BAD: missing heading: $h"
done
echo "heading check done"
```
Expected:
```
OK: FORKING.md rendered
OK: no Jinja residue
heading check done
```
(no `BAD:` lines)

> Note: the ```` ```bash ```` fenced blocks inside `FORKING.md.jinja` are literal
> Markdown — they contain no `{{ }}` or `{% %}`, so copier passes them through
> untouched. If you later add a Jinja expression inside a fence, wrap that fence
> in `{% raw %}`/`{% endraw %}`.

---

## Task 3: Detach-smoke step in `template-ci.yml`

**Files:**
- Modify: `.github/workflows/template-ci.yml` (append a new step at the end of the `render-and-gate` job)

**Interfaces:**
- Consumes: the `TEMPLATE-TRACKING` markers (Task 1) and the documented detach commands (Task 2). This step is the end-to-end test that ties both together.
- Produces: a CI guarantee that the documented detach yields the state issue #182's Verification block requires.

- [ ] **Step 1: Append the detach-smoke step to `template-ci.yml`**

Add this as the **last** step of the `render-and-gate` job (after the final existing step). It mutates `/tmp/smoke` in place, which is safe because the idempotence check and the gate already ran on the pristine render:

```yaml
      - name: detach smoke (FORKING.md commands produce a clean standalone state)
        working-directory: /tmp/smoke
        run: |
          # Mirrors the documented detach in the rendered FORKING.md. Runs LAST
          # because it mutates the tree in place; idempotence + gate already ran
          # on the pristine render. Asserts issue #182's Verification block.

          # --- Step 1: stop tracking ---
          rm -f .copier-answers.yml
          # --- Step 2: prune template-origin CI + fleet review wiring ---
          rm -f .github/workflows/copier-update.yml \
                .github/workflows/claude.yml \
                .github/workflows/claude-code-review.yml
          rm -rf .gemini
          # --- Step 3: scrub CLAUDE.md template-tracking blocks ---
          sed -i '/<!-- TEMPLATE-TRACKING-START -->/,/<!-- TEMPLATE-TRACKING-END -->/d' CLAUDE.md

          # --- assert the detached state ---
          [ ! -f .copier-answers.yml ] \
            || { echo "::error::.copier-answers.yml still present after detach"; exit 1; }
          ! grep -rn "copier" .github/ \
            || { echo "::error::copier reference remains under .github/ after detach"; exit 1; }
          ! grep -rniE "fleet|downstream conforms|shape lives in pvl-core" CLAUDE.md \
            || { echo "::error::fleet/downstream tracking language remains in CLAUDE.md"; exit 1; }
          grep -qE '^## Shared Infrastructure$' CLAUDE.md \
            && { echo "::error::Shared Infrastructure section survived the scrub"; exit 1; } || true
          grep -qE '^## Contributing fixes upstream$' CLAUDE.md \
            && { echo "::error::Contributing fixes upstream section survived the scrub"; exit 1; } || true
          grep -qF 'claude-review, gemini-code-assist' CLAUDE.md \
            && { echo "::error::bot-reviewer paragraph survived the scrub"; exit 1; } || true
          # neutral guidance must remain:
          grep -qE '^## Conventions$' CLAUDE.md \
            || { echo "::error::Conventions section lost — scrub deleted too much"; exit 1; }
          grep -qE '^## GitHub Review Types$' CLAUDE.md \
            || { echo "::error::GitHub Review Types section lost — scrub deleted too much"; exit 1; }
          # stripped files gone:
          for gone in \
              .github/workflows/copier-update.yml \
              .github/workflows/claude.yml \
              .github/workflows/claude-code-review.yml \
              .gemini; do
            [ ! -e "$gone" ] \
              || { echo "::error::$gone not removed by detach"; exit 1; }
          done
          # kept files present:
          for kept in \
              .github/workflows/ci.yml \
              .github/workflows/codeql.yml \
              .github/workflows/coverage-status.yml \
              .github/workflows/docs.yml \
              .github/workflows/release.yml; do
            [ -f "$kept" ] \
              || { echo "::error::$kept was removed but should be kept"; exit 1; }
          done
          echo "detach smoke passed"
```

> Note on the `grep ... && { ...; exit 1; } || true` idiom: a "must be absent"
> check cannot use `grep -q ... || { error }` (that errors when the pattern is
> *absent*, which is the success case). Instead, fire the error only when grep
> *matches*, and append `|| true` so a no-match (`grep` exit 1) does not trip
> `bash -e`.

- [ ] **Step 2: Verify the detach-smoke logic locally against a fresh render**

Run (this reproduces exactly what the CI step does):
```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
rm -f .copier-answers.yml
rm -f .github/workflows/copier-update.yml .github/workflows/claude.yml .github/workflows/claude-code-review.yml
rm -rf .gemini
sed -i '/<!-- TEMPLATE-TRACKING-START -->/,/<!-- TEMPLATE-TRACKING-END -->/d' CLAUDE.md
echo "--- issue #182 verification ---"
test ! -f .copier-answers.yml && echo "OK: copier answers removed"
grep -rn "copier" .github/ && echo "BAD: copier ref under .github/" || echo "OK: no copier refs under .github/"
grep -rniE "fleet|downstream conforms|shape lives in pvl-core" CLAUDE.md && echo "BAD: tracking language remains" || echo "OK: no tracking language"
grep -qE '^## Conventions$' CLAUDE.md && echo "OK: Conventions kept" || echo "BAD: Conventions lost"
cd -
```
Expected: every line is `OK:` (no `BAD:`).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/template-ci.yml
git commit -m "test(scaffold): CI smoke for clean template detach (refs #182)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Mark the spec implemented

**Files:**
- Modify: `docs/superpowers/specs/2026-06-20-template-detach-fork-design.md` (the `Status:` line)

- [ ] **Step 1: Flip the spec status**

Replace:
```markdown
- **Status:** Approved (design)
```
with:
```markdown
- **Status:** Implemented
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-06-20-template-detach-fork-design.md
git commit -m "docs(spec): mark template-detach design implemented (refs #182)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification (before opening the PR)

- [ ] **Run the full local gate on a detached render once more** to confirm nothing in the strip/scrub broke the pristine gate (the gate runs on the pristine tree; the detach is the last CI step):
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
  Expected: gate passes (FORKING.md and the markers do not affect ruff/mypy/pytest).

- [ ] **Open the PR** with `Closes #182` in the body (per the PR workflow, every PR closes an issue). The PR bundles all four commits on `feat/template-detach-fork`.

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Deliverable 1 (detach guide) → Task 2 (`FORKING.md.jinja`).
- Deliverable 2 (strip template-origin CI; document keep vs prune) → Task 2 Step 2 (guide) + Task 3 (CI asserts the prune; keep-set verified).
- Deliverable 3 (scrub opinionated `CLAUDE.md`) → Task 1 (markers) + Task 2 Step 3 (documented `sed`) + Task 3 (CI asserts scrub result and that neutral sections survive). `.claude/CLAUDE.md` is not rendered by the template; the guide notes a fork that added one applies the same scrub.
- Deliverable 4 (test/CI updates assert detached state) → Task 1 (marker-balance guard) + Task 3 (detach-smoke). No pre-existing smoke test asserts the old forking state, so nothing is rewritten/deleted — the new assertions are additive, matching the issue's "any … get updated" conditional.
- Issue Verification block → reproduced verbatim in Task 3 Steps 1–2.

**Placeholder scan:** none — every code/markdown block is complete and copy-pasteable.

**Type/string consistency:** marker strings (`<!-- TEMPLATE-TRACKING-START -->` / `-END -->`), the scrub `sed` range, and the strip/keep file lists are identical across Tasks 1, 2, and 3.
